
### Environment Interaction 1
----------------------------------------------------------------------------
```python
# Step 1: Get the supervisor's Spotify password
passwords = apis.supervisor.show_account_passwords()
spotify_password = [p["password"] for p in passwords if p["account_name"] == "spotify"][0]

# Step 2: Log in to Spotify to get the access token
login_result = apis.spotify.login(username='cheweber@gmail.com', password=spotify_password)
spotify_access_token = login_result["access_token"]

# Step 3: Get the current year and last year
from datetime import datetime
current_year = datetime.now().year
last_year = current_year - 1

# Step 4: Define a function to get all songs from paginated APIs
def get_all_songs(access_token):
    page_index = 0
    songs = []
    while True:
        song_page = apis.spotify.show_song_library(access_token=access_token, page_index=page_index)
        if not song_page:
            break
        songs.extend(song_page)
        page_index += 1
    return songs

# Step 5: Get all songs from the song library
songs = get_all_songs(spotify_access_token)

# Step 6: Define a function to get all albums from paginated APIs
def get_all_albums(access_token):
    page_index = 0
    albums = []
    while True:
        album_page = apis.spotify.show_album_library(access_token=access_token, page_index=page_index)
        if not album_page:
            break
        albums.extend(album_page)
        page_index += 1
    return albums

# Step 7: Get all albums from the album library
albums = get_all_albums(spotify_access_token)

# Step 8: Combine songs and albums into a single list of tracks
tracks = songs + albums

# Step 9: Count the number of tracks released in this or last year
count = 0
for track in tracks:
    release_year = int(track["release_date"][:4])
    if release_year in [current_year, last_year]:
        count += 1

# Step 10: Complete the task with the answer
apis.supervisor.complete_task(answer=count)
```

```
Execution failed. Traceback:
  File "<python-input>", line 50, in <module>
    release_year = int(track["release_date"][:4])
                       ~~~~~^^^^^^^^^^^^^^^^
KeyError: 'release_date'
```


### Environment Interaction 2
----------------------------------------------------------------------------
```python
# Check the API documentation for show_song_library
print(apis.api_docs.show_api_doc(app_name='spotify', api_name='show_song_library'))

# Check the API documentation for show_album_library
print(apis.api_docs.show_api_doc(app_name='spotify', api_name='show_album_library'))
```

```
{
 "app_name": "spotify",
 "api_name": "show_song_library",
 "path": "/spotify/library/songs",
 "method": "GET",
 "description": "Search or show a list of songs in your song library.",
 "parameters": [
  {
   "name": "access_token",
   "type": "string",
   "required": true,
   "description": "Access token obtained from spotify app login.",
   "default": null,
   "constraints": []
  },
  {
   "name": "query",
   "type": "string",
   "required": false,
   "description": "The search query string.",
   "default": "",
   "constraints": []
  },
  {
   "name": "page_index",
   "type": "integer",
   "required": false,
   "description": "The index of the page to return.",
   "default": 0,
   "constraints": [
    "value >= 0"
   ]
  },
  {
   "name": "page_limit",
   "type": "integer",
   "required": false,
   "description": "The maximum number of results to return per page.",
   "default": 5,
   "constraints": [
    "value >= 1, <= 20"
   ]
  },
  {
   "name": "sort_by",
   "type": "string",
   "required": false,
   "description": "The attribute to sort the library songs by prefixed with +/- to reflect ascending/descending. Valid attributes: added_at and title. If both query and sort_by are given and non-empty, results will be first ranked by query relevance, then paginated, and will then be sorted by the given attribute within each page. If both query and sort_by are not given, null, or empty, sort_by will default to -added_at.",
   "default": null,
   "constraints": []
  }
 ],
 "response_schemas": {
  "success": [
   {
    "song_id": 1,
    "title": "string",
    "album_id": 1,
    "album_title": "string",
    "duration": 1,
    "artists": [
     {
      "id": 1,
      "name": "string"
     }
    ],
    "added_at": "2019-01-01T00:00:00"
   }
  ],
  "failure": {
   "message": "string"
  }
 }
}
{
 "app_name": "spotify",
 "api_name": "show_album_library",
 "path": "/spotify/library/albums",
 "method": "GET",
 "description": "Search or show a list of albums in your album library.",
 "parameters": [
  {
   "name": "access_token",
   "type": "string",
   "required": true,
   "description": "Access token obtained from spotify app login.",
   "default": null,
   "constraints": []
  },
  {
   "name": "query",
   "type": "string",
   "required": false,
   "description": "The search query string.",
   "default": "",
   "constraints": []
  },
  {
   "name": "page_index",
   "type": "integer",
   "required": false,
   "description": "The index of the page to return.",
   "default": 0,
   "constraints": [
    "value >= 0"
   ]
  },
  {
   "name": "page_limit",
   "type": "integer",
   "required": false,
   "description": "The maximum number of results to return per page.",
   "default": 5,
   "constraints": [
    "value >= 1, <= 20"
   ]
  },
  {
   "name": "sort_by",
   "type": "string",
   "required": false,
   "description": "The attribute to sort the library albums by prefixed with +/- to reflect ascending/descending. Valid attributes: added_at and title. If both query and sort_by are given and non-empty, results will be first ranked by query relevance, then paginated, and will then be sorted by the given attribute within each page. If both query and sort_by are not given, null, or empty, sort_by will default to -added_at.",
   "default": null,
   "constraints": []
  }
 ],
 "response_schemas": {
  "success": [
   {
    "album_id": 1,
    "title": "string",
    "genre": "string",
    "artists": [
     {
      "id": 1,
      "name": "string"
     }
    ],
    "rating": 0.0,
    "like_count": 1,
    "review_count": 1,
    "release_date": "2019-01-01T00:00:00",
    "song_ids": [
     1
    ],
    "added_at": "2019-01-01T00:00:00"
   }
  ],
  "failure": {
   "message": "string"
  }
 }
}
```


### Environment Interaction 3
----------------------------------------------------------------------------
```python
# Step 1: Get the supervisor's Spotify password
passwords = apis.supervisor.show_account_passwords()
spotify_password = [p["password"] for p in passwords if p["account_name"] == "spotify"][0]

# Step 2: Log in to Spotify to get the access token
login_result = apis.spotify.login(username='cheweber@gmail.com', password=spotify_password)
spotify_access_token = login_result["access_token"]

# Step 3: Get the current year and last year
from datetime import datetime
current_year = datetime.now().year
last_year = current_year - 1

# Step 4: Define a function to get all albums from paginated APIs
def get_all_albums(access_token):
    page_index = 0
    albums = []
    while True:
        album_page = apis.spotify.show_album_library(access_token=access_token, page_index=page_index)
        if not album_page:
            break
        albums.extend(album_page)
        page_index += 1
    return albums

# Step 5: Get all albums from the album library
albums = get_all_albums(spotify_access_token)

# Step 6: Count the number of albums released in this or last year
count = 0
for album in albums:
    release_date_str = album["release_date"]
    release_year = int(release_date_str[:4])
    if release_year in [current_year, last_year]:
        count += 1

# Step 7: Complete the task with the answer
apis.supervisor.complete_task(answer=count)
```

```
Execution successful.
```

