──────────────────────────────── Overall Stats ─────────────────────────────────
Num Passed Tests : 4
Num Failed Tests : 1
Num Total  Tests : 5
──────────────────────────────────── Passes ────────────────────────────────────
>> Passed Requirement
assert answers match.
>> Passed Requirement
assert model changes match spotify.Song, spotify.SongLike.
>> Passed Requirement
assert all songs from artists main_user follows are liked now by using
private_data.followed_artist_song_ids.
>> Passed Requirement
assert none of the updated or removed song likes are from artists that main_user
follows,
using private_data.followed_artist_song_ids.
──────────────────────────────────── Fails ─────────────────────────────────────
>> Failed Requirement
assert all newly song likes are from artists that main_user follows via
models.changed_records
```python
with test(
    """
    assert all newly song likes are from artists that main_user follows via
models.changed_records
    """
):
    added_song_likes, updated_song_likes, removed_song_likes =
models.changed_records(
        "spotify.SongLike"
    )
```
----------
AssertionError:
197
in
[1, 2, 3, 4, 5, 6, 7, 29, 30, 31, 32, 70, 71, 72, 73, 77, 78, 79, 80, 81, 82,
93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 118, 119, 120, 121,
122, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 201,
202, 203, 204, 205, 206, 212, 213, 214, 215, 216, 217, 218, 219, 220, 259, 260,
261, 262, 263, 264, 265, 274, 275, 276, 277, 278, 279, 304, 305, 306, 307, 308]