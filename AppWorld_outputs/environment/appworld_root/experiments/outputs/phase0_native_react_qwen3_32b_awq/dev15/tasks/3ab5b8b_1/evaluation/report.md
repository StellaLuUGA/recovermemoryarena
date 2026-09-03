──────────────────────────────── Overall Stats ─────────────────────────────────
Num Passed Tests : 3
Num Failed Tests : 3
Num Total  Tests : 6
──────────────────────────────────── Passes ────────────────────────────────────
>> Passed Requirement
assert model changes match spotify.UserDownloadedSong.
>> Passed Requirement
obtain added, updated, removed spotify.UserDownloadedSong records using
models.changed_records,
and assert 0 have been removed.
>> Passed Requirement
assert all added downloaded song_ids are in private_data.library_song_ids
──────────────────────────────────── Fails ─────────────────────────────────────
>> Failed Requirement
assert answers match.
```python
with test(
    """
    assert answers match.
    """
):
    test.answer(predicted_answer, ground_truth_answer)
```
----------
AssertionError:  '<<not_given>>' == 'null'
>> Failed Requirement
assert added downloaded song_ids match private_data.to_download_song_ids
(ignore_order=True)
```python
with test(
    """
    assert added downloaded song_ids match private_data.to_download_song_ids
(ignore_order=True)
    """
):
    downloaded_song_ids = list_of(added_downloaded_songs, "song_id")
    test.case(downloaded_song_ids, "==", private_data.to_download_song_ids,
ignore_order=True)
```
----------
AssertionError:
[2, 48, 163, 165, 234, 292, 294]
==
[2, 11, 14, 27, 48, 94, 119, 131, 147, 173, 182, 190, 192, 197, 229, 233, 235,
251, 289, 303, 324]

In left but not right:
[163, 165, 234, 292, 294]

In right but not left:
[11, 14, 27, 94, 119, 131, 147, 173, 182, 190, 192, 197, 229, 233, 235, 251,
289, 303, 324]

Original values:
[294, 234, 292, 2, 165, 48, 163]
==
[192, 2, 131, 324, 197, 11, 14, 147, 27, 94, 289, 229, 233, 235, 173, 303, 48,
182, 119, 251, 190]
>> Failed Requirement
assert all added downloaded song_ids are in private_data.liked_song_ids
```python
with test(
    """
    assert all added downloaded song_ids are in private_data.liked_song_ids
    """
):
```
----------
AssertionError:
294
in
[2, 131, 135, 11, 14, 15, 142, 147, 21, 27, 30, 31, 289, 34, 35, 297, 173, 303,
48, 182, 190, 192, 320, 324, 197, 80, 81, 82, 94, 99, 100, 229, 233, 235, 117,
119, 251]