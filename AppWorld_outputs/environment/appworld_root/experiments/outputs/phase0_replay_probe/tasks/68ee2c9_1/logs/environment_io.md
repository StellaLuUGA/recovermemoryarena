
### Environment Interaction 1
----------------------------------------------------------------------------
```python
# Get the file system password from the supervisor app
passwords = apis.supervisor.show_account_passwords()
file_system_password = [p["password"] for p in passwords if p["account_name"] == "file_system"][0]

# Print the password for confirmation (optional)
print(file_system_password)
```

```
UJa-ovY
```


### Environment Interaction 2
----------------------------------------------------------------------------
```python
# Log in to the file system app
login_result = apis.file_system.login(username='nan_ritt@gmail.com', password=file_system_password)
print(login_result)
```

```
{
 "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmaWxlX3N5c3RlbStuYW5fcml0dEBnbWFpbC5jb20iLCJleHAiOjE2ODQ0MTIwOTh9.OXB9jZYGTZm1ICMcqz7zAhEldv23jPnlJXxe_HWbJ6c",
 "token_type": "Bearer"
}
```


### Environment Interaction 3
----------------------------------------------------------------------------
```python
# List all files in the ~/downloads/ directory
downloads_files = apis.file_system.list_files(path='~/downloads/', access_token=login_result['access_token'])
print(downloads_files)
```

```
Execution failed. Traceback:
  File "<python-input>", line 2, in <module>
    downloads_files = apis.file_system.list_files(path='~/downloads/', access_token=login_result['access_token'])
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^
Exception: No API named 'list_files' found in the file_system app.
```


### Environment Interaction 4
----------------------------------------------------------------------------
```python
# Get the list of APIs for the file_system app
print(apis.api_docs.show_api_descriptions(app_name='file_system'))
```

```
[
 {
  "name": "show_account",
  "description": "Show your account information. Unlike show_profile, this includes private information."
 },
 {
  "name": "signup",
  "description": "Sign up to create account."
 },
 {
  "name": "delete_account",
  "description": "Delete your account."
 },
 {
  "name": "update_account_name",
  "description": "Update your first or last name in the account profile."
 },
 {
  "name": "login",
  "description": "Login to your account."
 },
 {
  "name": "logout",
  "description": "Logout from your account."
 },
 {
  "name": "send_verification_code",
  "description": "Send account verification code to your email address."
 },
 {
  "name": "verify_account",
  "description": "Verify your account using the verification code sent to your email address."
 },
 {
  "name": "send_password_reset_code",
  "description": "Send password reset code to your email address."
 },
 {
  "name": "reset_password",
  "description": "Reset your password using the password reset code sent to your email address."
 },
 {
  "name": "show_profile",
  "description": "Show public profile information of a user."
 },
 {
  "name": "create_directory",
  "description": "Create a directory if it does not exist, optionally recursively."
 },
 {
  "name": "delete_directory",
  "description": "Delete a directory with its sub-directories and files."
 },
 {
  "name": "show_directory",
  "description": "Show a list of files and/or sub-directories, optionally recursively, in a directory."
 },
 {
  "name": "directory_exists",
  "description": "Check if a directory exists."
 },
 {
  "name": "show_file",
  "description": "Show a file's content and other details, if it exists."
 },
 {
  "name": "create_file",
  "description": "Create a new file with the given content."
 },
 {
  "name": "update_file",
  "description": "Update a file's content."
 },
 {
  "name": "delete_file",
  "description": "Delete a file."
 },
 {
  "name": "file_exists",
  "description": "Check if a file exists."
 },
 {
  "name": "copy_file",
  "description": "Copy a file to another location."
 },
 {
  "name": "move_file",
  "description": "Move a file to another location."
 },
 {
  "name": "copy_directory",
  "description": "Copy a directory to another location."
 },
 {
  "name": "move_directory",
  "description": "Move a directory to another location."
 },
 {
  "name": "compress_directory",
  "description": "Compress a directory."
 },
 {
  "name": "decompress_file",
  "description": "Decompress a compressed file."
 }
]
```


### Environment Interaction 5
----------------------------------------------------------------------------
```python
# Get the specifications for the show_directory API
print(apis.api_docs.show_api_doc(app_name='file_system', api_name='show_directory'))
```

```
{
 "app_name": "file_system",
 "api_name": "show_directory",
 "path": "/file_system/directory",
 "method": "GET",
 "description": "Show a list of files and/or sub-directories, optionally recursively, in a directory.",
 "parameters": [
  {
   "name": "access_token",
   "type": "string",
   "required": true,
   "description": "Access token obtained from file_system app login.",
   "default": null,
   "constraints": []
  },
  {
   "name": "directory_path",
   "type": "string",
   "required": false,
   "description": "Path of the directory. Path can be absolute, starting with '/', or relative to the user's home directory, starting with '~/'.",
   "default": "/",
   "constraints": [
    "length >= 1"
   ]
  },
  {
   "name": "substring",
   "type": "string",
   "required": false,
   "description": "If passed, only files and sub-directories containing the given substring (ignoring case) will be shown.",
   "default": null,
   "constraints": []
  },
  {
   "name": "entry_type",
   "type": "string",
   "required": false,
   "description": "Whether to show all files and sub-directories, only files, or only sub-directories.",
   "default": "all",
   "constraints": [
    "value in ['all', 'files', 'directories']"
   ]
  },
  {
   "name": "recursive",
   "type": "boolean",
   "required": false,
   "description": "Whether to show files recursively.",
   "default": true,
   "constraints": []
  }
 ],
 "response_schemas": {
  "success": [
   "string"
  ],
  "failure": {
   "message": "string"
  }
 }
}
```


### Environment Interaction 6
----------------------------------------------------------------------------
```python
# List all files in the ~/downloads/ directory
downloads_files = apis.file_system.show_directory(
    access_token=login_result['access_token'],
    directory_path='~/downloads/',
    entry_type='files'
)
print(downloads_files)
```

```
[
 "/home/nancy/downloads/DIY_home_repair_guide.docx",
 "/home/nancy/downloads/art_inspiration_sketches.zip",
 "/home/nancy/downloads/bike_lights.jpg",
 "/home/nancy/downloads/bike_pump.jpg",
 "/home/nancy/downloads/board_games.jpg",
 "/home/nancy/downloads/candy.pdf",
 "/home/nancy/downloads/car_repair_sibling.pdf",
 "/home/nancy/downloads/chairs.jpg",
 "/home/nancy/downloads/chalk_bag.pdf",
 "/home/nancy/downloads/childhood_memories.zip",
 "/home/nancy/downloads/chocolate.jpg",
 "/home/nancy/downloads/clean_up_supplies.jpg",
 "/home/nancy/downloads/cleaning_supplies.jpg",
 "/home/nancy/downloads/climbing_shoes.jpg",
 "/home/nancy/downloads/concert_programs.jpg",
 "/home/nancy/downloads/concert_t_shirt.jpg",
 "/home/nancy/downloads/cooking_tips_and_tricks_videos.zip",
 "/home/nancy/downloads/cute_cat_gifs_collection.gif",
 "/home/nancy/downloads/cycling_shorts.jpg",
 "/home/nancy/downloads/dads_new_phone.pdf",
 "/home/nancy/downloads/data_visualization_examples.ppt",
 "/home/nancy/downloads/delicious_recipe_videos.zip",
 "/home/nancy/downloads/dinner_date.jpg",
 "/home/nancy/downloads/dinner_party.jpg",
 "/home/nancy/downloads/dinner_party_cousins.jpg",
 "/home/nancy/downloads/dog_food.jpg",
 "/home/nancy/downloads/dumbbells.jpg",
 "/home/nancy/downloads/earplugs.pdf",
 "/home/nancy/downloads/emergency_fund.jpg",
 "/home/nancy/downloads/escape_room_merchandise.pdf",
 "/home/nancy/downloads/family_photoshoot.jpg",
 "/home/nancy/downloads/fashion_design_inspiration_gallery.zip",
 "/home/nancy/downloads/fashion_design_sketches.rar",
 "/home/nancy/downloads/financial_growth_analysis.xlsx",
 "/home/nancy/downloads/first_aid_kit.jpg",
 "/home/nancy/downloads/fitness_tracker.jpg",
 "/home/nancy/downloads/foam_roller.pdf",
 "/home/nancy/downloads/food_processor.pdf",
 "/home/nancy/downloads/game_expansion_pack.jpg",
 "/home/nancy/downloads/game_night.jpg",
 "/home/nancy/downloads/garden_decor.pdf",
 "/home/nancy/downloads/gardening_book.jpg",
 "/home/nancy/downloads/gas_bill.pdf",
 "/home/nancy/downloads/groceries_receipt.jpg",
 "/home/nancy/downloads/guide_service.jpg",
 "/home/nancy/downloads/health_checkup.jpg",
 "/home/nancy/downloads/hobby_supplies.jpg",
 "/home/nancy/downloads/holiday_baking_supplies.pdf",
 "/home/nancy/downloads/houseplants.jpg",
 "/home/nancy/downloads/ice_bucket.pdf",
 "/home/nancy/downloads/ice_cream.jpg",
 "/home/nancy/downloads/kitchen_utensils.jpg",
 "/home/nancy/downloads/language_learning_podcasts.mp3",
 "/home/nancy/downloads/marketing_materials.jpg",
 "/home/nancy/downloads/marketing_materials.pdf",
 "/home/nancy/downloads/medical_insurance.pdf",
 "/home/nancy/downloads/meeting_room_rental.jpg",
 "/home/nancy/downloads/merchandise.jpg",
 "/home/nancy/downloads/mindfulness_meditation_audio_sessions.mp3",
 "/home/nancy/downloads/moms_new_dress.jpg",
 "/home/nancy/downloads/monthly_groceries.jpg",
 "/home/nancy/downloads/mulch.pdf",
 "/home/nancy/downloads/new_dress.jpg",
 "/home/nancy/downloads/new_sofa.jpg",
 "/home/nancy/downloads/new_years_eve_party.jpg",
 "/home/nancy/downloads/ocean_wave_relaxation_audio.mp3",
 "/home/nancy/downloads/office_decorations.jpg",
 "/home/nancy/downloads/office_lighting.pdf",
 "/home/nancy/downloads/office_stationery.jpg",
 "/home/nancy/downloads/office_utilities.pdf",
 "/home/nancy/downloads/online_course.pdf",
 "/home/nancy/downloads/photography_competition_entries.rar",
 "/home/nancy/downloads/portable_charger.pdf",
 "/home/nancy/downloads/punch_bowl.jpg",
 "/home/nancy/downloads/puzzle_solvers_guide.pdf",
 "/home/nancy/downloads/recipe_collection.pdf",
 "/home/nancy/downloads/saddle_bag.pdf",
 "/home/nancy/downloads/scientific_research_paper.pdf",
 "/home/nancy/downloads/shower_curtain.pdf",
 "/home/nancy/downloads/ski_insurance.pdf",
 "/home/nancy/downloads/space_exploration_videos.zip",
 "/home/nancy/downloads/subscription_service.jpg",
 "/home/nancy/downloads/supplements.pdf",
 "/home/nancy/downloads/table_rentals.pdf",
 "/home/nancy/downloads/team_lunch.jpg",
 "/home/nancy/downloads/timers.pdf",
 "/home/nancy/downloads/toiletries.jpg",
 "/home/nancy/downloads/training_course.jpg",
 "/home/nancy/downloads/transportation.pdf",
 "/home/nancy/downloads/travel_adventure_diary.docx",
 "/home/nancy/downloads/travel_adventures_journal.doc",
 "/home/nancy/downloads/trellis.pdf",
 "/home/nancy/downloads/vacuum_cleaner.pdf",
 "/home/nancy/downloads/virtual_reality_gaming_experience.zip",
 "/home/nancy/downloads/volunteer_t_shirts.jpg",
 "/home/nancy/downloads/wine_charms.pdf",
 "/home/nancy/downloads/wine_opener.jpg",
 "/home/nancy/downloads/workout_progress_tracker.doc",
 "/home/nancy/downloads/world_landmarks_photo_album.zip",
 "/home/nancy/downloads/world_travel_itinerary.docx"
]
```


### Environment Interaction 7
----------------------------------------------------------------------------
```python
from datetime import datetime

# Get the current year
current_year = datetime.now().year

# Process each file
for file_path in downloads_files:
    # Get file details including creation date
    file_details = apis.file_system.show_file(access_token=login_result['access_token'], file_path=file_path)
    creation_date = file_details.get('created_at')

    # Format the date as YYYY-MM-DD
    formatted_date = datetime.strptime(creation_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")

    # Create the new file name with the date prefix
    new_file_name = f"{formatted_date}_{file_path.split('/')[-1]}"

    # Construct the new file path
    new_file_path = file_path.replace(file_path.split('/')[-1], new_file_name)

    # Rename the file
    apis.file_system.move_file(
        access_token=login_result['access_token'],
        source_path=file_path,
        destination_path=new_file_path
    )

    # Check if the file was created this year
    if int(creation_date.split('-')[0]) != current_year:
        # Move the file to ~/trash/
        trash_path = f"~/trash/{new_file_name}"
        apis.file_system.move_file(
            access_token=login_result['access_token'],
            source_path=new_file_path,
            destination_path=trash_path
        )
```

```
Execution failed. Traceback:
  File "<python-input>", line 13, in <module>
    formatted_date = datetime.strptime(creation_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ValueError: time data '2022-12-04T10:24:57' does not match format '%Y-%m-%d %H:%M:%S'
```


### Environment Interaction 8
----------------------------------------------------------------------------
```python
from datetime import datetime

# Get the current year
current_year = datetime.now().year

# Process each file
for file_path in downloads_files:
    # Get file details including creation date
    file_details = apis.file_system.show_file(access_token=login_result['access_token'], file_path=file_path)
    creation_date = file_details.get('created_at')

    # Parse the ISO 8601 date format
    parsed_date = datetime.fromisoformat(creation_date)

    # Format the date as YYYY-MM-DD
    formatted_date = parsed_date.strftime("%Y-%m-%d")

    # Create the new file name with the date prefix
    new_file_name = f"{formatted_date}_{file_path.split('/')[-1]}"

    # Construct the new file path
    new_file_path = file_path.replace(file_path.split('/')[-1], new_file_name)

    # Rename the file
    apis.file_system.move_file(
        access_token=login_result['access_token'],
        source_path=file_path,
        destination_path=new_file_path
    )

    # Check if the file was created this year
    if parsed_date.year != current_year:
        # Move the file to ~/trash/
        trash_path = f"~/trash/{new_file_name}"
        apis.file_system.move_file(
            access_token=login_result['access_token'],
            source_path=new_file_path,
            destination_path=trash_path
        )
```

```
Execution failed. Traceback:
  File "<python-input>", line 25, in <module>
    apis.file_system.move_file(
Exception: Unexpected parameter 'source_path' passed to the move_file API of the file_system app. Allowed parameters are: ['source_file_path', 'destination_file_path', 'access_token', 'overwrite', 'retain_dates']
```


### Environment Interaction 9
----------------------------------------------------------------------------
```python
from datetime import datetime

# Get the current year
current_year = datetime.now().year

# Process each file
for file_path in downloads_files:
    # Get file details including creation date
    file_details = apis.file_system.show_file(access_token=login_result['access_token'], file_path=file_path)
    creation_date = file_details.get('created_at')

    # Parse the ISO 8601 date format
    parsed_date = datetime.fromisoformat(creation_date)

    # Format the date as YYYY-MM-DD
    formatted_date = parsed_date.strftime("%Y-%m-%d")

    # Create the new file name with the date prefix
    new_file_name = f"{formatted_date}_{file_path.split('/')[-1]}"

    # Construct the new file path
    new_file_path = file_path.replace(file_path.split('/')[-1], new_file_name)

    # Rename the file
    apis.file_system.move_file(
        access_token=login_result['access_token'],
        source_file_path=file_path,
        destination_file_path=new_file_path
    )

    # Check if the file was created this year
    if parsed_date.year != current_year:
        # Move the file to ~/trash/
        trash_path = f"~/trash/{new_file_name}"
        apis.file_system.move_file(
            access_token=login_result['access_token'],
            source_file_path=new_file_path,
            destination_file_path=trash_path
        )
```

```
Execution successful.
```


### Environment Interaction 10
----------------------------------------------------------------------------
```python
# Mark the task as complete
apis.supervisor.complete_task()
```

```
Execution successful.
```

