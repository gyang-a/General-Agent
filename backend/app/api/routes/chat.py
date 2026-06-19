from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.runtime import AgentRunInput, AgentRunState, stream_agent_events
from app.dependencies import require_auth
from app.schemas.chat import ChatStreamRequest
from app.services.message_service import persist_assistant_message, persist_user_message
from app.services.model_service import available_models, resolve_selection_for_user
from app.services.rag_service import retrieve_context
from app.utils.sse import sse_event

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(payload: ChatStreamRequest, auth: dict = Depends(require_auth)) -> StreamingResponse:
    username = auth["username"]
    if not payload.conversation_id or not payload.message:
        raise HTTPException(status_code=400, detail="conversationId 和 message 为必填")

    selection = await resolve_selection_for_user(username, payload.model)
    if not selection:
        models = await available_models(username)
        raise HTTPException(status_code=400, detail=f"模型不可用，请从已配置模型中选择：{', '.join(models['models'])}")

    provider = selection["provider"]
    resolved_model = selection["model"]
    if not provider.get("endpoint"):
        raise HTTPException(status_code=500, detail="上游接口地址不能为空，请检查模型 Provider 配置")

    await persist_user_message(
        username,
        payload.conversation_id,
        payload.message,
        payload.attachments,
        resolved_model,
    )

    async def events() -> AsyncIterator[str]:
        state = AgentRunState()
        rag_payload = {
            "promptContext": "",
            "refs": [],
            "contextDocs": [],
            "retrievalModeUsed": "none",
        }
        try:
            yield ": connected\n\n"

            pinned_doc_ids = [str(item.get("docId") or "").strip() for item in payload.attachments]
            pinned_doc_ids = [item for item in pinned_doc_ids if item]
            rag_payload = await retrieve_context(
                username=username,
                query=payload.message,
                pinned_doc_ids=pinned_doc_ids,
                retrieval_mode=payload.retrieval_mode,
                top_k=payload.rag_top_k,
            )

            yield sse_event(
                {
                    "refs": rag_payload["refs"],
                    "contextDocs": rag_payload["contextDocs"],
                    "retrievalModeUsed": rag_payload["retrievalModeUsed"],
                }
            )

            state.refs = rag_payload["refs"]
            state.context_docs = rag_payload["contextDocs"]
            run_input = AgentRunInput(
                username=username,
                provider=provider,
                model=resolved_model,
                conversation_id=payload.conversation_id,
                message=payload.message,
                rag_context=rag_payload["promptContext"],
                use_web_search=payload.use_web_search,
                refs=rag_payload["refs"],
                context_docs=rag_payload["contextDocs"],
                retrieval_mode_used=rag_payload["retrievalModeUsed"],
            )
            async for event in stream_agent_events(
                run_input=run_input,
                state=state,
            ):
                yield sse_event(event)

            if state.content and not state.error and not state.aborted:
                await persist_assistant_message(
                    username,
                    payload.conversation_id,
                    state.content,
                    state.refs,
                    state.context_docs,
                    rag_payload["retrievalModeUsed"],
                    state.usage,
                )
        except Exception as exc:
            state.error = str(exc) or "聊天生成失败"
            yield sse_event({"error": state.error})
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream; charset=utf-8")
