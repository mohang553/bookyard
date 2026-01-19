# app/api/v1/datasets.py
from fastapi import APIRouter, HTTPException, status
from pathlib import Path
import logging
from typing import Optional

from app.schemas.dataset_schemas import (
    DatasetLoadRequest,
    DatasetLoadResponse,
    DatasetStatusResponse,
    RecommendationRequest,
    RecommendationResponse
)
from app.services.dataset_service import DatasetService
from app.services.recommendation_engine import RecommendationEngine

router = APIRouter(
    prefix="/api/v1/datasets",
    tags=["datasets"],
    responses={404: {"description": "Not found"}}
)

logger = logging.getLogger(__name__)

# Configuration
DATA_FOLDER = Path(__file__).parent.parent.parent.parent / "data"

@router.post(
    "/load",
    response_model=DatasetLoadResponse,
    summary="Load datasets",
    description="Load Books, Ratings, and Users datasets from local folder or uploaded files"
)
async def load_datasets(request: DatasetLoadRequest):
    """
    Load datasets for the recommendation system from /data folder.
    
    **Parameters:**
    - source: "local" (loads from /data folder)
    - nrows: Optional number of rows to load (default: 15000)
    
    **Expected files in /data folder:**
    - Books.csv
    - Book-Ratings.csv
    - Users.csv
    """
    
    try:
        dataset_service = DatasetService()
        
        # Load from /data folder
        books_path = DATA_FOLDER / "Books.csv"
        ratings_path = DATA_FOLDER / "Book-Ratings.csv"
        users_path = DATA_FOLDER / "Users.csv"
        
        # Verify files exist
        missing_files = []
        for name, file_path in [
            ("Books.csv", books_path),
            ("Book-Ratings.csv", ratings_path),
            ("Users.csv", users_path)
        ]:
            if not file_path.exists():
                missing_files.append(f"{name} (expected at: {file_path})")
        
        if missing_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Missing files in /data folder: {', '.join(missing_files)}"
            )
        
        logger.info(f"Loading datasets from {DATA_FOLDER}")
        result = dataset_service.load_datasets(
            books_path=str(books_path),
            ratings_path=str(ratings_path),
            users_path=str(users_path),
            nrows=request.nrows
        )
        
        return DatasetLoadResponse(
            status=result["status"],
            message=result["message"],
            statistics=result.get("statistics")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading datasets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading datasets: {str(e)}"
        )

@router.get(
    "/status",
    response_model=DatasetStatusResponse,
    summary="Check dataset status",
    description="Check if datasets are loaded and get basic statistics"
)
async def get_dataset_status():
    """
    Get current status of loaded datasets.
    
    **Returns:**
    - status: "loaded" or "not_loaded"
    - statistics: Users, books, and total ratings count
    """
    try:
        dataset_service = DatasetService()
        status_info = dataset_service.get_status()
        return DatasetStatusResponse(**status_info)
    
    except Exception as e:
        logger.error(f"Error getting dataset status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting dataset status: {str(e)}"
        )

@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Get book recommendations",
    description="Generate personalized book recommendations for a specific user"
)
async def get_recommendations(request: RecommendationRequest):
    """
    Get personalized book recommendations for a user.
    
    Uses collaborative filtering based on similar users' ratings.
    
    **Parameters:**
    - user_id: User ID to get recommendations for (required)
    - k: Number of similar users to consider (default: 10)
    - top_n: Number of books to recommend (default: 10)
    
    **Returns:**
    - List of recommended books with details and predicted ratings
    """
    
    try:
        dataset_service = DatasetService()
        
        if not dataset_service.is_loaded():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Datasets not loaded. Please load datasets first using /load endpoint"
            )
        
        recommendations = RecommendationEngine.get_recommendations_dict(
            user_id=request.user_id,
            k=request.k,
            top_n=request.top_n
        )
        
        if recommendations["status"] == "error":
            return RecommendationResponse(
                status="error",
                user_id=request.user_id,
                message=recommendations["message"]
            )
        
        return RecommendationResponse(**recommendations)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating recommendations: {str(e)}"
        )

@router.get(
    "/users",
    summary="Get available users",
    description="Get list of available user IDs for recommendations"
)
async def get_available_users(limit: int = 20):
    """
    Get available user IDs from loaded datasets.
    
    **Parameters:**
    - limit: Number of user IDs to return (default: 20)
    
    **Returns:**
    - List of user IDs that can be used for recommendations
    """
    try:
        dataset_service = DatasetService()
        
        if not dataset_service.is_loaded():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Datasets not loaded. Please load datasets first using /load endpoint"
            )
        
        user_ids = list(dataset_service._user_book_matrix.index[:limit])
        
        return {
            "status": "success",
            "total_available_users": len(dataset_service._user_book_matrix),
            "sample_user_ids": user_ids,
            "limit_requested": limit
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user IDs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user IDs: {str(e)}"
        )

# Health check endpoint
@router.get(
    "/health",
    summary="Health check",
    description="Check if the datasets service is running"
)
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "ok",
        "service": "datasets-recommendation"
    }