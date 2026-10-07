#AI log, entry format: date, AI type used, prompt/purpose, modifications
    #prompt (if more detail is required)

#30/09/2026, VS Code chat, used AI to write code and explain said code for the app.py and index.html files (frontend and backend). Changed the modules the AI gave, using as working skeleton. Further changes to be made. 
    #Prompt: "using csv, jsonify, and os, write code that will have three sections; one for browsing and searching a collection by name, one for searching and browsing a list of locations, and one that will show graphs and a timeline. The section for browsing and searching a collection needs to read the csv file draft collection works.csv and show a list of works by title and author. Each title should be clickable to learn more about the work. When you click a work title the work should display the following information: work title, author, type of work, aboriginal heritage, aboriginal group location, work medium, date created, collection it belongs to, and where the work is housed. The second section for browsing and searching a list of locations should use the csv file draft places.csv. The page should show 8 buttons, one for each state and a view all. When these are clicked it should lead to a list of places in that state, which should be listed by name and address. Each place should be clickable and will show the following information when clicked; name, address, indigenous exclusive content, indigenous owned or run, and sourced by. The third section should be titled 'Art Centres over time', and should show a line graph for how many indigenous art centres have developed over time taken from the 'year founded' column in draft places.csv, and a bar graph that shows how many places are indigenous owned and run vs not, taken from the column"

#30/09/2026, VS Code chat, used AI to reorganise and combine column information for display purposes in cvs file draft places.csv. 
    #Prompt: "Can you combine the columns aboriginal group location, and state in draft collection.csv, separating the information in them by a comma?" 

#06/10/2026, gemini, used AI to check the project directory structure and see if other files are needed and what their file purposes would be, took on some advice (created a Procfile and requirements.txt), discarded others.
    #Prompt: "I have an assignment to create an app using python using the following prompts and guidlines: 'Create an app with three sections; one for browsing and searching a collection by name, one for searching and browsing a list of locations, and one that will show graphs and a timeline.' I also need to include a file called readme.md and AI-log.md. What should my working directory look like?"

#06/10/2026, VS Code, used AI to write code for user registration for saving a list that only a logged in user could see, asked it to change which type it used (PostgreSQL to SQLite)
    #Prompt: 'write code in app.py and index.html that lets users add places to a saved list. Only a logged in user should be able to see and edit their list, the list should not be visible to other users. Please modify the funtion myplaces to do so.' 

#07/10/2026, VS Code, used AI to add a function to my app code to give an option of making a recovery account to reset password. Asked it to explain the code, checked code, note * tests in test_app.py were automatically created during this process, these were not included in count for required tests as they were not intentionally created, but they were checked 
    #Prompt: Can you add code so that when you create a user account, there is an option of making a recover email to reset the password if you fail to login? Explain the code

#07/10/2026, VS Code, used AI to write me code for testing the app's response to a csv file with missing information and to explain that code
    #Prompt: Write a function in test_app.py that will test if app.py crashes or returns 'file not found' when a data entry in the csv file is missing or incomplete. Explain each line of code. 

#07/10/2026, VS Code, used AI to correct my code and explain why my mistakes wouldn't work
    #Prompt: Could you check my code for def test_login_failure_incorrect_password in test_app.py and see if it works? If not, could you explain why?

#07/10/2026, VS Code, used AI to restructure my code so that each page has its own html file, instead of sharing one file, checked the code, added pages and app routes for better app formatting
    #Prompt: Can you split-up the template's index.html file into a html file for each 'tab', and ensure that the test and app functions align with this new formatting? Please explain any changes to app.py that you make for this