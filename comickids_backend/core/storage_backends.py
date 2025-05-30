import os
import uuid
from datetime import datetime
from django.core.files.storage import Storage
from django.conf import settings
from supabase import create_client, Client
from django.core.files.base import ContentFile
import requests
from io import BytesIO

class SupabaseStorage(Storage):
    def __init__(self):
        try:
            self.supabase: Client = create_client(
                settings.SUPABASE_URL, 
                settings.SUPABASE_SERVICE_KEY
            )
            self.bucket_name = settings.SUPABASE_STORAGE_BUCKET
        except Exception as e:
            print(f"Failed to initialize Supabase client: {e}")
            raise

    def _save(self, name, content):
        """Save file to Supabase Storage"""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(name)[1]
            unique_name = f"{timestamp}_{uuid.uuid4().hex[:8]}{file_extension}"
            
            # Read content
            content.seek(0)
            file_data = content.read()
            
            # Upload to Supabase
            try:
                result = self.supabase.storage.from_(self.bucket_name).upload(
                    unique_name, 
                    file_data,
                    file_options={"content-type": self._get_content_type(file_extension)}
                )
                
                # Check if upload was successful
                if hasattr(result, 'status_code'):
                    if result.status_code == 200:
                        return unique_name
                    else:
                        raise Exception(f"Upload failed with status {result.status_code}: {result}")
                else:
                    # Supabase might return different response format
                    print(f"Upload result: {result}")
                    return unique_name
                    
            except Exception as upload_error:
                print(f"Supabase upload error: {upload_error}")
                raise Exception(f"Failed to upload to Supabase: {upload_error}")
                
        except Exception as e:
            print(f"Error in _save method: {e}")
            raise

    def _get_content_type(self, extension):
        """Get content type based on file extension"""
        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return content_types.get(extension.lower(), 'application/octet-stream')

    def delete(self, name):
        """Delete file from Supabase Storage"""
        try:
            result = self.supabase.storage.from_(self.bucket_name).remove([name])
            # Handle different response formats
            if hasattr(result, 'status_code'):
                return result.status_code == 200
            else:
                # Check if deletion was successful by other means
                return True
        except Exception as e:
            print(f"Error deleting from Supabase: {e}")
            return False

    def exists(self, name):
        """Check if file exists in Supabase Storage"""
        try:
            result = self.supabase.storage.from_(self.bucket_name).list(
                path="", 
                search=name
            )
            return len(result) > 0 if result else False
        except Exception as e:
            print(f"Error checking file existence: {e}")
            return False

    def url(self, name):
        """Return the public URL for the file"""
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/{self.bucket_name}/{name}"

    def size(self, name):
        """Get file size"""
        try:
            response = requests.head(self.url(name), timeout=10)
            return int(response.headers.get('Content-Length', 0))
        except Exception as e:
            print(f"Error getting file size: {e}")
            return 0
    def __init__(self):
        self.supabase: Client = create_client(
            settings.SUPABASE_URL, 
            settings.SUPABASE_SERVICE_KEY
        )
        self.bucket_name = settings.SUPABASE_STORAGE_BUCKET

    def _save(self, name, content):
        """Save file to Supabase Storage"""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(name)[1]
            unique_name = f"{timestamp}_{uuid.uuid4().hex[:8]}{file_extension}"
            
            # Read content
            content.seek(0)
            file_data = content.read()
            
            # Upload to Supabase
            result = self.supabase.storage.from_(self.bucket_name).upload(
                unique_name, 
                file_data,
                file_options={"content-type": self._get_content_type(file_extension)}
            )
            
            if result.status_code == 200:
                return unique_name
            else:
                raise Exception(f"Upload failed: {result}")
                
        except Exception as e:
            print(f"Error uploading to Supabase: {e}")
            raise

    def _get_content_type(self, extension):
        """Get content type based on file extension"""
        content_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return content_types.get(extension.lower(), 'application/octet-stream')

    def delete(self, name):
        """Delete file from Supabase Storage"""
        try:
            result = self.supabase.storage.from_(self.bucket_name).remove([name])
            return result.status_code == 200
        except Exception as e:
            print(f"Error deleting from Supabase: {e}")
            return False

    def exists(self, name):
        """Check if file exists in Supabase Storage"""
        try:
            result = self.supabase.storage.from_(self.bucket_name).list(
                path="", 
                search=name
            )
            return len(result) > 0
        except:
            return False

    def url(self, name):
        """Return the public URL for the file"""
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/{self.bucket_name}/{name}"

    def size(self, name):
        """Get file size"""
        try:
            response = requests.head(self.url(name))
            return int(response.headers.get('Content-Length', 0))
        except:
            return 0