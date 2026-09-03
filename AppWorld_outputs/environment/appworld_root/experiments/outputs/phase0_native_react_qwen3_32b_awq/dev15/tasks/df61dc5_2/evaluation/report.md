──────────────────────────────── Overall Stats ─────────────────────────────────
Num Passed Tests : 6
Num Failed Tests : 1
Num Total  Tests : 7
──────────────────────────────────── Passes ────────────────────────────────────
>> Passed Requirement
assert answers match.
>> Passed Requirement
assert model changes match venmo.Transaction, venmo.TransactionLike
>> Passed Requirement
obtain added, updated, removed venmo.Transaction records using
models.changed_records,
and assert 0 transactions were added or removed.
>> Passed Requirement
assert updated transactions have only changed in like_count field using
models.changed_field_names.
>> Passed Requirement
obtain added, updated, removed venmo.TransactionLike records using
models.changed_records,
and assert 0 transaction likes were removed.
>> Passed Requirement
assert all updated transactions were created after
private_data.min_transaction_datetime
──────────────────────────────────── Fails ─────────────────────────────────────
>> Failed Requirement
assert set of updated transaction ids match exactly to
private_data.to_like_transaction_ids (ignore order).
```python
with test(
    """
    assert set of updated transaction ids match exactly to
    private_data.to_like_transaction_ids (ignore order).
    """
):
    updated_transaction_ids = unique_list_of(updated_transactions, "id")
    test.case(
```
----------
AssertionError:
[1082, 1122, 8229, 8238, 8241, 8245]
==
[1067, 1082, 1086, 1087, 1107, 1108, 1115, 1120, 1122, 2642, 4444, 4450, 4492,
5984, 5986, 6343, 8229, 8231, 8232, 8234, 8237, 8239, 8243, 8246]

In left but not right:
[8238, 8241, 8245]

In right but not left:
[1067, 1086, 1087, 1107, 1108, 1115, 1120, 2642, 4444, 4450, 4492, 5984, 5986,
6343, 8231, 8232, 8234, 8237, 8239, 8243, 8246]

Original values:
[1082, 1122, 8229, 8238, 8241, 8245]
==
[1107, 1108, 1115, 1120, 1122, 4444, 4450, 5984, 5986, 6343, 8229, 8232, 8243,
1067, 1082, 1086, 1087, 2642, 4492, 8231, 8234, 8237, 8239, 8246]