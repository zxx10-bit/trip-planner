"""POI相关API路由"""

import base64
import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from ...services.amap_service import get_amap_service, search_attraction_photo
from ...services.unsplash_service import get_unsplash_service

router = APIRouter(prefix="/poi", tags=["POI"])


class POIDetailResponse(BaseModel):
    """POI详情响应"""
    success: bool
    message: str
    data: Optional[dict] = None


@router.get(
    "/detail/{poi_id}",
    response_model=POIDetailResponse,
    summary="获取POI详情",
    description="根据POI ID获取详细信息,包括图片"
)
async def get_poi_detail(poi_id: str):
    """
    获取POI详情
    
    Args:
        poi_id: POI ID
        
    Returns:
        POI详情响应
    """
    try:
        amap_service = get_amap_service()
        
        # 调用高德地图POI详情API
        result = amap_service.get_poi_detail(poi_id)
        
        return POIDetailResponse(
            success=True,
            message="获取POI详情成功",
            data=result
        )
        
    except Exception as e:
        print(f"❌ 获取POI详情失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取POI详情失败: {str(e)}"
        )


@router.get(
    "/search",
    summary="搜索POI",
    description="根据关键词搜索POI"
)
async def search_poi(keywords: str, city: str = "北京"):
    """
    搜索POI

    Args:
        keywords: 搜索关键词
        city: 城市名称

    Returns:
        搜索结果
    """
    try:
        amap_service = get_amap_service()
        result = amap_service.search_poi(keywords, city)

        return {
            "success": True,
            "message": "搜索成功",
            "data": result
        }

    except Exception as e:
        print(f"❌ 搜索POI失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"搜索POI失败: {str(e)}"
        )


@router.get(
    "/photo",
    summary="获取景点图片",
    description="根据景点名称获取图片,优先使用高德(国内可访问),Unsplash作为兜底"
)
async def get_attraction_photo(name: str, city: Optional[str] = None):
    """
    获取景点图片

    Args:
        name: 景点名称
        city: 城市名称(可选)

    Returns:
        图片URL
    """
    try:
        # 优先从高德获取(国内直连、速度快)
        photo_url = search_attraction_photo(name, city)

        # 高德没有图片时,兜底使用Unsplash
        if not photo_url:
            unsplash_service = get_unsplash_service()

            # 搜索景点图片
            photo_url = unsplash_service.get_photo_url(f"{name} China landmark")

            if not photo_url:
                # 如果没找到,尝试只用景点名称搜索
                photo_url = unsplash_service.get_photo_url(name)

        return {
            "success": True,
            "message": "获取图片成功",
            "data": {
                "name": name,
                "photo_url": photo_url
            }
        }

    except Exception as e:
        print(f"❌ 获取景点图片失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"获取景点图片失败: {str(e)}"
        )


@router.get(
    "/image-proxy",
    summary="图片代理",
    description="后端代理下载远程图片并返回base64,用于前端html2canvas截图时绕开跨域问题"
)
async def image_proxy(
    url: str = Query(..., description="远程图片URL"),
    max_size: int = Query(5, description="最大图片大小(MB),超过则拒绝")
):
    """
    图片代理 - 服务端下载远程图片转base64返回

    Args:
        url: 远程图片的完整URL
        max_size: 最大允许大小(MB)

    Returns:
        base64 data URL
    """
    try:
        # 安全检查:只允许http/https
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="只支持http/https协议的URL")

        # 下载图片
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "image/*"
                }
            )
            resp.raise_for_status()

            # 大小检查
            max_bytes = max_size * 1024 * 1024
            if len(resp.content) > max_bytes:
                raise HTTPException(status_code=413, detail=f"图片超过{max_size}MB限制")

            # 获取 content-type,默认 image/jpeg
            content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
            if not content_type.startswith("image/"):
                content_type = "image/jpeg"

            # 转 base64
            b64 = base64.b64encode(resp.content).decode("utf-8")
            data_url = f"data:{content_type};base64,{b64}"

            return {
                "success": True,
                "url": data_url,
                "content_type": content_type,
                "size_bytes": len(resp.content)
            }

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"图片服务器返回错误: {e.response.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="下载图片超时")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片代理失败: {str(e)}")

