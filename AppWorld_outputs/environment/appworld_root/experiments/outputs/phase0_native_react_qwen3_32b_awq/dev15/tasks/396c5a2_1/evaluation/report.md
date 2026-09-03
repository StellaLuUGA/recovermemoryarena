──────────────────────────────── Overall Stats ─────────────────────────────────
Num Passed Tests : 5
Num Failed Tests : 1
Num Total  Tests : 6
──────────────────────────────────── Passes ────────────────────────────────────
>> Passed Requirement
assert answers match.
>> Passed Requirement
assert model changes match spotify.MusicPlayer.
>> Passed Requirement
assert 1 spotify.MusicPlayer has been updated using models.changed_records.
>> Passed Requirement
get the end-state queue_song_ids and
assert all private_data.existing_queue_song_ids are in end-state queue_song_ids.
>> Passed Requirement
assert all private_data.to_be_added_queue_song_ids are in the end state
queue_song_ids
──────────────────────────────────── Fails ─────────────────────────────────────
>> Failed Requirement
assert union of private_data.to_be_added_queue_song_ids and
private_data.existing_queue_song_ids
match the end-state queue_song_ids.
```python
with test(
    """
    assert union of private_data.to_be_added_queue_song_ids and
private_data.existing_queue_song_ids
    match the end-state queue_song_ids.
    """
):
    test.case(
        set(private_data.existing_queue_song_ids +
private_data.to_be_added_queue_song_ids),
```
----------
AssertionError:
{102, 38, 202, 10, 108, 114, 214, 311, 285, 287}
==
{257, 194, 102, 38, 202, 10, 108, 142, 114, 51, 214, 311, 88, 185, 285, 287}

In right but not left:
[257, 194, 142, 51, 88, 185]