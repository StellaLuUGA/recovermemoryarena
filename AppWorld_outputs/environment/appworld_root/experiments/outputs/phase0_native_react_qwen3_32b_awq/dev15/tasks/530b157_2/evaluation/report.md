──────────────────────────────── Overall Stats ─────────────────────────────────
Num Passed Tests : 5
Num Failed Tests : 5
Num Total  Tests : 10
──────────────────────────────────── Passes ────────────────────────────────────
>> Passed Requirement
assert answers match.
>> Passed Requirement
obtain added, updated, deleted venmo.Transactions using models.changed_records
assert 1 is added, 0 is updated, and 0 is deleted.
>> Passed Requirement
assert the added transaction receiver_id is private_data.friend_venmo_user_id.
>> Passed Requirement
assert the added transaction has description public_data.note.
>> Passed Requirement
assert none of the records from phone.UserTextMessage have been deleted
──────────────────────────────────── Fails ─────────────────────────────────────
>> Failed Requirement
assert model changes match venmo.Transaction, phone.GlobalTextMessage,
phone.UserTextMessage,
ignoring venmo.User and venmo.Notification
```python
with test(
    """
    assert model changes match venmo.Transaction, phone.GlobalTextMessage,
phone.UserTextMessage,
    ignoring venmo.User and venmo.Notification
    """
):
    changed_model_names = models.changed_model_names(
        ignore=["venmo.User", "venmo.Notification"]
```
----------
AssertionError:
{'venmo.Transaction'}
==
{'phone.UserTextMessage', 'phone.GlobalTextMessage', 'venmo.Transaction'}

In right but not left:
['phone.UserTextMessage', 'phone.GlobalTextMessage']
>> Failed Requirement
assert the added transaction has amount private_data.grocery_cost.
```python
with test(
    """
    assert the added transaction has amount private_data.grocery_cost.
    """
):
    test.case(added_transaction.amount, "==", private_data.grocery_cost)
```
----------
AssertionError:  100.0 == 98
>> Failed Requirement
obtain added, updated, deleted phone.GlobalTextMessage using
models.changed_records
assert 1 is added, 0 is updated, and 0 is deleted.
```python
with test(
    """
    obtain added, updated, deleted phone.GlobalTextMessage using
models.changed_records
    assert 1 is added, 0 is updated, and 0 is deleted.
    """
):
    (
        added_global_text_messages,
```
----------
AssertionError:  0 == 1
>> Failed Requirement
assert the added global_text_message's receiver_id is to
private_data.friend_phone_user_id.
```python
with test(
    """
    assert the added global_text_message's receiver_id is to
private_data.friend_phone_user_id.
    """
):
    added_global_text_message = added_global_text_messages[0]
    test.case(added_global_text_message.receiver_id, "==",
private_data.friend_phone_user_id)
```
----------
>> Failed Requirement
assert the added global_text_message has message, public_data.message_text
(ignore case).
```python
with test(
    """
    assert the added global_text_message has message, public_data.message_text
(ignore case).
    """
):
    test.case(
        added_global_text_message.message, "==", public_data.message_text,
ignore_case=True
    )
```
----------