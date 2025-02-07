import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import schedule
import time
from pathlib import Path
import toml
import json
import sys

def check_password(password_app, password):
    """Returns `True` if the user had the correct password."""
    if password_app == password:
        return True
    else:
        return False

# Function to update data at the beginning of each week
def update_data():
    
    # Read the variables from secrets.toml
    password_app = st.secrets.password_app
    key = st.secrets.key
    sheet_key = st.secrets.sheet_key

    # Debug mode check
    debug_mode = "debug" in sys.argv
    if debug_mode:
        st.write("DEBUG MODE ACTIVE")
        st.write(f"Current secrets loaded: password_app exists: {bool(password_app)}, key exists: {bool(key)}, sheet_key exists: {bool(sheet_key)}")

    # Check if the sheet is already in the session state
    if 'sheet' not in st.session_state:
        # Convert the string to a dictionary
        key_dict = json.loads(key) 
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        client = gspread.authorize(credentials)
        # Open the Google Sheets document for the correct week
        st.session_state.sheet = client.open_by_key(sheet_key)
        if debug_mode:
            st.write("Sheet connection established")
            st.write(f"Available worksheets: {[ws.title for ws in st.session_state.sheet.worksheets()]}")

    current_date = datetime.date.today()

    # Define the reference start date (Sunday, January 12, 2025)
    start_date = datetime.date(2025, 1, 12)
    
    # Calculate the number of weeks, ensuring each Sunday starts a new week
    week_number = ((current_date - start_date).days // 7) + 1
    week_number = (current_date - datetime.date(2025, 1, 11)).days // 7 + 2 
    # Calculate the days until the next Sunday (0: Monday, 1: Tuesday, ..., 6: Sunday)
    days_until_sunday = (6 - current_date.weekday()) % 7

    if debug_mode:
        st.write(f"Current date: {current_date}")
        st.write(f"Current week number: {week_number} - {type(week_number)}")
        st.write(f"Days until Sunday: {days_until_sunday}")

    # Get the date of the next Sunday
    next_sunday_date = (current_date + datetime.timedelta(days=days_until_sunday)).strftime('%B %d %Y')
    st.session_state.count = 0
    try:
        # Access the sheet for the current week from Google Sheets
        current_worksheet = st.session_state.sheet.worksheet(f"{week_number}")  # Get worksheet by name
        current_data = [row[0:2] for row in current_worksheet.get_all_values()[1:]]

        if debug_mode:
            st.write(f"Current worksheet title: {current_worksheet.title}")
            st.write(f"Raw worksheet data: {current_data}")

        # Read the content of the specified cell
        try:
            cell_content = current_worksheet.acell('B1').value
            if debug_mode:
                st.write(f"Cell B1 content: {cell_content}")
        except gspread.exceptions.CellNotFound:
            cell_content = None
            if debug_mode:
                st.write("Cell B1 not found")

        if (cell_content is not None) and (st.session_state.count == 0):
            # Set the app title
            st.session_state.count = 1
            st.title(f"This Week's CG Sabal Chase Meal Theme: {cell_content}")
            
            st.write(f"Here is the new way we are doing meal sign-ups! It automatically updates each Monday with the up-coming Sunday food items so please use this same link every week. Please sign up for an item to bring for this Sunday, {next_sunday_date} and share the link with whoever is interested. If you have any questions, please reach out to Kenzie. Thank you!")
            st.write("")
            
            next_week_theme = current_worksheet.acell('E2').value
            st.write("For those who meal plan, next week's theme is: ", next_week_theme)
            
            st.image('dtgville.jpg')

            st.write("")

            st.subheader("Food/Drink Items Still Needed")

            # Display the "Food/Drink Item" and "Name" columns from the second row
            df = pd.DataFrame(current_data[1:], columns=current_data[0])
            st.dataframe(df, height=500, width=500)
            st.write("")
            
            if debug_mode:
                st.write("Current DataFrame contents:")
                st.write(df)
            
            st.subheader("Sign Up for an Item")
            # User interface for signing up
            item_to_bring = st.multiselect("Select an item to bring", df[df["Name - Dish"] == ""]["Food/Drink Item"])
            
            if len(item_to_bring) > 0:
                user_name = st.text_input("Your Name")

                if st.button("Submit", "submit food items"):
                    # Update the "Signed Up" column in the Google Sheet with the user's name for the selected item
                    user_name_str  = str(user_name)
                    item_indices = df.index[df["Food/Drink Item"].isin(item_to_bring)].to_list()

                    if debug_mode:
                        st.write(f"Attempting to update items: {item_to_bring}")
                        st.write(f"For user: {user_name_str}")
                        st.write(f"At indices: {item_indices}")

                    # Check if the cell already has a value
                    for item_index in item_indices:
                        df.at[item_index, 'Name'] = user_name
                        cell_value = current_worksheet.acell(f'B{item_index + 3}').value
                        if cell_value:
                            st.error(f"Someone is already bringing that! Please sign up for a different item :) ")
                            if debug_mode:
                                st.write(f"Conflict detected at index {item_index}, cell already contains: {cell_value}")
                        else:
                            cell = current_worksheet.acell(f'B{item_index + 3}')  
                            cell.value = user_name_str  # Setting the new value
                            current_worksheet.update_cell(cell.row, cell.col, cell.value)
                            if debug_mode:
                                st.write(f"Successfully updated cell B{item_index + 3} with value: {user_name_str}")
                        
                    st.success(f"Thank {user_name} for signing up to bring {item_to_bring}! Please refresh the page to see the updated list.")
                    st.image('fountain.jpg')

        else:
            st.warning("Sheet for the current week is empty - sorry! Please message Kenzie and let her know :) ")
            if debug_mode:
                st.write("Sheet empty condition triggered")
                st.write(f"cell_content: {cell_content}")
                st.write(f"session_state.count: {st.session_state.count}")

    except gspread.exceptions.WorksheetNotFound:
        # Handle the case where the sheet for the current week is not found
        st.error(f"Sheet for week {week_number} not found")
        if debug_mode:
            st.write("WorksheetNotFound exception triggered")
            st.write(f"Attempted to access week number: {week_number}")

# Schedule automatic updates at the beginning of each week (Monday)
schedule.every().monday.at('00:00').do(update_data)

# Run the app
if __name__ == '__main__':
    update_data()  # Run the update_data function when the app starts

    while True:
        schedule.run_pending()
        time.sleep(1)

# import streamlit as st
# import gspread
# from oauth2client.service_account import ServiceAccountCredentials
# import pandas as pd
# import datetime
# import json
# import sys

# # Function to load data from Google Sheets
# def update_data(group_selection):
#     # Read secrets
#     key = st.secrets.key
#     sheet_key = st.secrets.sheet_key

#     # Connect to Google Sheets
#     if 'sheet' not in st.session_state:
#         key_dict = json.loads(key)
#         scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
#         credentials = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
#         client = gspread.authorize(credentials)
#         st.session_state.sheet = client.open_by_key(sheet_key)

#     # Get current date for week calculation
#     current_date = datetime.date.today()
#     start_date = datetime.date(2025, 1, 12)  # First Sunday
#     week_number = ((current_date - start_date).days // 7) + 2
#     days_until_sunday = (6 - current_date.weekday()) % 7
#     next_sunday_date = (current_date + datetime.timedelta(days=days_until_sunday)).strftime('%B %d %Y')

#     try:
#         # Fetch the current worksheet based on the calculated week number
#         current_worksheet = st.session_state.sheet.worksheet(f"{week_number}")
#         all_data = current_worksheet.get_all_values()

#         # Extract Theme from B1
#         theme = all_data[0][1] if len(all_data) > 1 else "No theme available"

#         # Extract headers (A2:C2)
#         headers = all_data[1] if len(all_data) > 1 else ["Food/Drink Item", "CG SABAL CHASE", "CG HANDS"]

#         # Extract data rows (A3:C)
#         data_rows = all_data[2:] if len(all_data) > 3 else []

#         # Convert data into a DataFrame
#         df = pd.DataFrame(data_rows, columns=headers)

#         # Ensure required columns exist
#         if "Food/Drink Item" not in df.columns:
#             st.warning("The sheet format is incorrect. Make sure 'Food/Drink Item' starts in column A3.")
#             return

#         # Determine which column to read/write based on CG selection
#         if group_selection == "CG SABAL CHASE":
#             name_column_letter = "B"  # SC Signups go into Column B
#             name_column_index = "CG SABAL CHASE"
#         else:  # CG HANDS
#             name_column_letter = "C"  # Hands Signups go into Column C
#             name_column_index = "CG HANDS"

#         # Store session state variables
#         st.session_state.week_number = week_number
#         st.session_state.next_sunday_date = next_sunday_date
#         st.session_state.current_worksheet = current_worksheet
#         st.session_state.theme = theme
#         st.session_state.df = df
#         st.session_state.name_column_letter = name_column_letter
#         st.session_state.name_column_index = name_column_index

#     except gspread.exceptions.WorksheetNotFound:
#         st.warning(f"Sheet for week {week_number} not found.")
#         return


# # UI Layout
# st.title("CG Meal Sign-Up")

# # Group selection dropdown
# group_selection = st.selectbox("Select Your CG:", ["CG SABAL CHASE", "CG HANDS"], key="group_selection")

# # Run update_data() when the user selects a group
# if st.session_state.get("selected_group") != group_selection:
#     update_data(group_selection)
#     st.session_state.selected_group = group_selection

# if "df" in st.session_state:
#     df = st.session_state.df

#     st.header(f"{group_selection} - This Week's Meal Theme: **{st.session_state.theme}** 🍽️")
#     st.write(
#         f"Sign up for an item to bring for this Sunday, **{st.session_state.next_sunday_date}**."
#     )

#     # Display an image
#     st.image("dtgville.jpg", caption="Meal Planning")

#     st.subheader("🍔 Food/Drink Items Still Needed")

#     # Show only unclaimed items for the selected CG
#     df_filtered = df[df[st.session_state.name_column_index] == ""]  # Only show empty rows

#     if df_filtered.empty:
#         st.info("✅ All food items have been signed up for! Thank you!")
#     else:
#         st.dataframe(df_filtered[["Food/Drink Item"]], height=500, width=500)

#         st.subheader("✅ Sign Up for an Item")
#         available_items = df_filtered["Food/Drink Item"]
        
#         item_to_bring = st.multiselect(
#             "Select an item to bring:", available_items, key="food_selection"
#         )

#         user_name = st.text_input("Your Name", key="user_name_input")

#         if st.button("Submit", key="submit_button"):
#             if item_to_bring and user_name:
#                 # Update the Google Sheet with the user's name
#                 worksheet = st.session_state.current_worksheet
#                 updated_count = 0

#                 for index, row in df.iterrows():
#                     if row["Food/Drink Item"] in item_to_bring:
#                         cell_address = f'{st.session_state.name_column_letter}{index + 3}'  # +3 because data starts at A3
#                         current_value = worksheet.acell(cell_address).value
#                         if current_value:  # Someone already signed up
#                             st.error(f"⚠️ Someone already signed up for {row['Food/Drink Item']}! Choose another item.")
#                         else:
#                             worksheet.update_acell(cell_address, user_name)
#                             updated_count += 1

#                 if updated_count > 0:
#                     st.success(f"Thank you, {user_name}, for signing up to bring {', '.join(item_to_bring)}!")
#                     st.image("fountain.jpg", caption="Thank You!")
#             else:
#                 st.error("⚠️ Please select at least one item and enter your name.")
# else:
#     st.warning("⚠️ No data available for this week. Please message Kenzie to check the sheet!")
