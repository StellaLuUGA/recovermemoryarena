──────────────────────────────── Overall Stats ─────────────────────────────────
Num Passed Tests : 4
Num Failed Tests : 1
Num Total  Tests : 5
──────────────────────────────────── Passes ────────────────────────────────────
>> Passed Requirement
assert answers match.
>> Passed Requirement
assert model changes match phone.GlobalTextMessage, phone.UserTextMessage
>> Passed Requirement
assert 0 phone.UserTextMessage records were removed.
>> Passed Requirement
assert all added global text messages have message public_data.message_text
(normalize_text=True).
──────────────────────────────────── Fails ─────────────────────────────────────
>> Failed Requirement
assert receiver_ids of added global text messages match exactly to
private_data.no_account_phone_user_ids (ignore order).
```python
with test(
    """
    assert receiver_ids of added global text messages match exactly to
    private_data.no_account_phone_user_ids (ignore order).
    """
):
    added_global_text_messages, _, _ =
models.changed_records("phone.GlobalTextMessage")
    added_receiver_ids = list_of(added_global_text_messages, "receiver_id")
```
----------
AssertionError:  [41, 42, 43, 46, 90] == [42, 46]

In left but not right:
[41, 43, 90]

Original values:
[90, 43, 46, 41, 42] == [42, 46]