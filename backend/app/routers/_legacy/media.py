"""
Remotion media generation endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.deps import require_minimum_role
from app.schemas import (
    RemotionAssistantRunRequest,
    RemotionAssistantRunResponse,
    RemotionHealthResponse,
    RemotionPresetCreateRequest,
    RemotionPresetResponse,
    RemotionPresetUpdateRequest,
    RemotionRenderRequest,
    RemotionRenderResponse,
    RemotionSuggestRequest,
    RemotionSuggestResponse,
    RemotionTemplateResponse,
)
from app.services.media_remotion import (
    delete_preset,
    get_health,
    list_artifacts,
    list_saved_presets,
    list_templates,
    render_media,
    resolve_artifact,
    run_assistant_media_request,
    save_preset,
    suggest_from_brief,
    update_preset,
)

router = APIRouter(prefix="/media/remotion", tags=["Remotion Media"])


@router.get("/health", response_model=RemotionHealthResponse)
async def remotion_health(
    _current_user=Depends(require_minimum_role("operator")),
):
    return get_health()


@router.get("/templates", response_model=list[RemotionTemplateResponse])
async def remotion_templates(
    _current_user=Depends(require_minimum_role("operator")),
):
    return list_templates()


@router.get("/presets", response_model=list[RemotionPresetResponse])
async def remotion_presets(
    current_user=Depends(require_minimum_role("operator")),
):
    return list_saved_presets(current_user.tenant_id)


@router.post(
    "/presets",
    response_model=RemotionPresetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def remotion_save_preset(
    body: RemotionPresetCreateRequest,
    current_user=Depends(require_minimum_role("operator")),
):
    return save_preset(body, current_user.tenant_id)


@router.delete("/presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remotion_delete_preset(
    preset_id: str,
    current_user=Depends(require_minimum_role("operator")),
):
    removed = delete_preset(preset_id, current_user.tenant_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found")


@router.put("/presets/{preset_id}", response_model=RemotionPresetResponse)
async def remotion_update_preset(
    preset_id: str,
    body: RemotionPresetUpdateRequest,
    current_user=Depends(require_minimum_role("operator")),
):
    updated = update_preset(preset_id, body, current_user.tenant_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found")
    return updated


@router.post("/render", response_model=RemotionRenderResponse)
async def remotion_render(
    body: RemotionRenderRequest,
    request: Request,
    current_user=Depends(require_minimum_role("operator")),
):
    artifact = await render_media(body, current_user.tenant_id)
    asset_url = str(request.url_for("remotion_asset", file_name=artifact.file_name))
    download_url = str(request.url_for("remotion_download", file_name=artifact.file_name))
    return RemotionRenderResponse(
        job_id=artifact.job_id,
        kind=artifact.kind,
        template_id=artifact.template_id,
        file_name=artifact.file_name,
        mime_type=artifact.mime_type,
        width=artifact.width,
        height=artifact.height,
        fps=artifact.fps,
        duration_in_frames=artifact.duration_in_frames,
        created_at=artifact.created_at,
        asset_url=asset_url,
        download_url=download_url,
    )


@router.post("/suggest", response_model=RemotionSuggestResponse)
async def remotion_suggest(
    body: RemotionSuggestRequest,
    _current_user=Depends(require_minimum_role("operator")),
):
    return await suggest_from_brief(body)


@router.post("/assistant-run", response_model=RemotionAssistantRunResponse)
async def remotion_assistant_run(
    body: RemotionAssistantRunRequest,
    request: Request,
    current_user=Depends(require_minimum_role("operator")),
):
    suggestion, artifact, summary = await run_assistant_media_request(body, current_user.tenant_id)
    render = RemotionRenderResponse(
        job_id=artifact.job_id,
        kind=artifact.kind,
        template_id=artifact.template_id,
        file_name=artifact.file_name,
        mime_type=artifact.mime_type,
        width=artifact.width,
        height=artifact.height,
        fps=artifact.fps,
        duration_in_frames=artifact.duration_in_frames,
        created_at=artifact.created_at,
        asset_url=str(request.url_for("remotion_asset", file_name=artifact.file_name)),
        download_url=str(request.url_for("remotion_download", file_name=artifact.file_name)),
    )
    return RemotionAssistantRunResponse(
        summary=summary,
        suggestion=suggestion,
        render=render,
    )


@router.get("/renders", response_model=list[RemotionRenderResponse])
async def remotion_render_history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(require_minimum_role("operator")),
):
    artifacts = list_artifacts(limit=limit, tenant_id=current_user.tenant_id)
    return [
        RemotionRenderResponse(
            job_id=artifact.job_id,
            kind=artifact.kind,
            template_id=artifact.template_id,
            file_name=artifact.file_name,
            mime_type=artifact.mime_type,
            width=artifact.width,
            height=artifact.height,
            fps=artifact.fps,
            duration_in_frames=artifact.duration_in_frames,
            created_at=artifact.created_at,
            asset_url=str(request.url_for("remotion_asset", file_name=artifact.file_name)),
            download_url=str(request.url_for("remotion_download", file_name=artifact.file_name)),
        )
        for artifact in artifacts
    ]


@router.get("/renders/{file_name}", name="remotion_asset")
async def remotion_asset(
    file_name: str,
    current_user=Depends(require_minimum_role("operator")),
):
    artifact = resolve_artifact(file_name, current_user.tenant_id)
    media_type = "image/png" if artifact.suffix.lower() == ".png" else "video/mp4"
    return FileResponse(path=artifact, media_type=media_type, filename=artifact.name)


@router.get("/renders/{file_name}/download", name="remotion_download")
async def remotion_download(
    file_name: str,
    current_user=Depends(require_minimum_role("operator")),
):
    artifact = resolve_artifact(file_name, current_user.tenant_id)
    media_type = "image/png" if artifact.suffix.lower() == ".png" else "video/mp4"
    return FileResponse(
        path=artifact,
        media_type=media_type,
        filename=artifact.name,
    )
