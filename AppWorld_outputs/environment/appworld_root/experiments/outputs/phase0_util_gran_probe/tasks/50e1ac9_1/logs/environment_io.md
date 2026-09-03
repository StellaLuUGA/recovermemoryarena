
### Environment Interaction 1
----------------------------------------------------------------------------
```python
print(apis.api_docs.show_app_descriptions())
```

```
[
 {
  "name": "api_docs",
  "description": "An app to search and explore API documentation."
 },
 {
  "name": "supervisor",
  "description": "An app to access supervisor's personal information, account credentials, addresses, payment cards, and manage the assigned task."
 },
 {
  "name": "amazon",
  "description": "An online shopping app to buy products and manage orders, returns, etc."
 },
 {
  "name": "phone",
  "description": "An app to find and manage contact information for friends, family members, etc., send and receive messages, and manage alarms."
 },
 {
  "name": "file_system",
  "description": "A file system app to create and manage files and folders."
 },
 {
  "name": "spotify",
  "description": "A music streaming app to stream songs and manage song, album and playlist libraries."
 },
 {
  "name": "venmo",
  "description": "A social payment app to send, receive and request money to and from others."
 },
 {
  "name": "gmail",
  "description": "An email app to draft, send, receive, and manage emails."
 },
 {
  "name": "splitwise",
  "description": "A bill splitting app to track and split expenses with people."
 },
 {
  "name": "simple_note",
  "description": "A note-taking app to create and manage notes."
 },
 {
  "name": "todoist",
  "description": "A task management app to manage todo lists and collaborate on them with others."
 }
]
```


### Environment Interaction 2
----------------------------------------------------------------------------
```python
print(apis.supervisor.show_account_passwords())
```

```
[
 {
  "account_name": "amazon",
  "password": "kz0d(by"
 },
 {
  "account_name": "file_system",
  "password": "ym=Rysn"
 },
 {
  "account_name": "gmail",
  "password": "H9c5f9I"
 },
 {
  "account_name": "phone",
  "password": "F#_2d^6"
 },
 {
  "account_name": "simple_note",
  "password": "}@}a=$h"
 },
 {
  "account_name": "splitwise",
  "password": "FMLx3Hu"
 },
 {
  "account_name": "spotify",
  "password": "EbhXe%D"
 },
 {
  "account_name": "todoist",
  "password": "JBfGOar"
 },
 {
  "account_name": "venmo",
  "password": "zp$44pd"
 }
]
```


### Environment Interaction 3
----------------------------------------------------------------------------
```python
print(apis.supervisor.show_profile())
```

```
{
 "first_name": "Glenn",
 "last_name": "Burton",
 "email": "glenn.burton@gmail.com",
 "phone_number": "8638518861",
 "birthday": "1993-08-13",
 "sex": "male"
}
```

