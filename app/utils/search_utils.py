from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import re
import asyncio
from pymongo import DESCENDING
from app.models.message_search import MessageSearch
from app.models.messages import Message


class SearchIndexer:
    """
    Utility class for managing message search indexing
    """
    
    @staticmethod
    async def index_message(message: Message, username: str, room_name: Optional[str] = None, participants: List[int] = None) -> MessageSearch:
        """
        Index a single message for search
        """
        return await MessageSearch.create_from_message(
            message=message,
            username=username,
            room_name=room_name,
            participants=participants
        )
    
    @staticmethod
    async def bulk_index_messages(messages_data: List[Dict[str, Any]]) -> List[MessageSearch]:
        """
        Bulk index multiple messages
        messages_data format: [
            {
                'message': Message,
                'username': str,
                'room_name': Optional[str],
                'participants': List[int]
            }
        ]
        """
        tasks = []
        for data in messages_data:
            task = MessageSearch.create_from_message(
                message=data['message'],
                username=data['username'],
                room_name=data.get('room_name'),
                participants=data.get('participants', [])
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return list(results)
    
    @staticmethod
    async def update_search_index(message_id: str, **update_data) -> Optional[MessageSearch]:
        """
        Update existing search index entry
        """
        search_doc = await MessageSearch.find_one({"message_id": message_id})
        if search_doc:
            return await search_doc.update_search_data(**update_data)
        return None
    
    @staticmethod
    async def remove_from_search_index(message_id: str) -> bool:
        """
        Remove message from search index
        """
        search_doc = await MessageSearch.find_one({"message_id": message_id})
        if search_doc:
            await search_doc.delete()
            return True
        return False


class SearchQueryBuilder:
    """
    Utility class for building search queries
    """
    
    @staticmethod
    def build_text_search_query(query: str) -> str:
        """
        Build optimized text search query
        """
        # Remove special characters and normalize
        query = re.sub(r'[^\w\s]', ' ', query)
        query = ' '.join(query.split())  # Remove extra spaces
        
        # Add phrase search for exact matches
        if len(query.split()) > 1:
            return f'"{query}" {query}'
        
        return query
    
    @staticmethod
    def build_filter_conditions(
        user_id: int,
        room_id: Optional[int] = None,
        room_type: Optional[str] = None,
        message_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build filter conditions for search
        """
        conditions = {
            "is_searchable": True,
            "$or": [
                {"participants": user_id},
                {"room_type": "group", "is_searchable": True}
            ]
        }
        
        if room_id:
            conditions["room_id"] = room_id
            
        if room_type:
            conditions["room_type"] = room_type
            
        if message_type:
            conditions["message_type"] = message_type
            
        if language:
            conditions["language"] = language
        
        # Date range filtering
        if date_from or date_to:
            date_filter = {}
            if date_from:
                date_filter["$gte"] = date_from
            if date_to:
                date_filter["$lte"] = date_to
            conditions["message_created_at"] = date_filter
        
        return conditions


class SearchAnalytics:
    """
    Utility class for search analytics and optimization
    """
    
    @staticmethod
    async def get_search_statistics() -> Dict[str, Any]:
        """
        Get search index statistics
        """
        total_docs = await MessageSearch.count()
        
        # Count by room type
        private_count = await MessageSearch.find({"room_type": "private"}).count()
        group_count = await MessageSearch.find({"room_type": "group"}).count()
        
        # Count by message type
        text_count = await MessageSearch.find({"message_type": "text"}).count()
        image_count = await MessageSearch.find({"message_type": "image"}).count()
        file_count = await MessageSearch.find({"message_type": "file"}).count()
        
        # Count searchable vs non-searchable
        searchable_count = await MessageSearch.find({"is_searchable": True}).count()
        
        return {
            "total_documents": total_docs,
            "by_room_type": {
                "private": private_count,
                "group": group_count
            },
            "by_message_type": {
                "text": text_count,
                "image": image_count,
                "file": file_count
            },
            "searchable_documents": searchable_count,
            "non_searchable_documents": total_docs - searchable_count
        }
    
    @staticmethod
    async def get_popular_keywords(limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get most popular keywords from search index
        """
        pipeline = [
            {"$match": {"is_searchable": True}},
            {"$unwind": "$content_keywords"},
            {"$group": {
                "_id": "$content_keywords",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": DESCENDING}},
            {"$limit": limit},
            {"$project": {
                "keyword": "$_id",
                "frequency": "$count",
                "_id": 0
            }}
        ]
        
        result = await MessageSearch.aggregate(pipeline).to_list()
        return result
    
    @staticmethod
    async def cleanup_old_search_entries(days_old: int = 90) -> int:
        """
        Clean up old search entries that are no longer needed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        old_entries = await MessageSearch.find({
            "indexed_at": {"$lt": cutoff_date},
            "is_searchable": False
        }).to_list()
        
        deleted_count = 0
        for entry in old_entries:
            await entry.delete()
            deleted_count += 1
        
        return deleted_count


# Search API helper functions
async def search_messages_advanced(
    query: str,
    user_id: int,
    room_id: Optional[int] = None,
    room_type: Optional[str] = None,
    message_type: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    language: Optional[str] = None,
    limit: int = 50,
    skip: int = 0
) -> List[MessageSearch]:
    """
    Advanced message search with multiple filters
    """
    # Build search query
    search_query = SearchQueryBuilder.build_text_search_query(query)
    
    # Build filter conditions
    filter_conditions = SearchQueryBuilder.build_filter_conditions(
        user_id=user_id,
        room_id=room_id,
        room_type=room_type,
        message_type=message_type,
        date_from=date_from,
        date_to=date_to,
        language=language
    )
    
    # Add text search if query provided
    if search_query:
        filter_conditions["$text"] = {"$search": search_query}
    
    # Execute search
    results = await MessageSearch.find(filter_conditions).sort([
        ("search_priority", DESCENDING),
        ("message_created_at", DESCENDING)
    ]).skip(skip).limit(limit).to_list()
    
    return results


async def get_search_suggestions(partial_query: str, user_id: int, limit: int = 10) -> List[str]:
    """
    Get search suggestions based on partial query
    """
    if len(partial_query) < 2:
        return []
    
    # Search in keywords that start with the partial query
    pipeline = [
        {"$match": {
            "is_searchable": True,
            "$or": [
                {"participants": user_id},
                {"room_type": "group", "is_searchable": True}
            ]
        }},
        {"$unwind": "$content_keywords"},
        {"$match": {
            "content_keywords": {"$regex": f"^{re.escape(partial_query.lower())}", "$options": "i"}
        }},
        {"$group": {
            "_id": "$content_keywords",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": DESCENDING}},
        {"$limit": limit},
        {"$project": {"suggestion": "$_id", "_id": 0}}
    ]
    
    results = await MessageSearch.aggregate(pipeline).to_list()
    return [result["suggestion"] for result in results]