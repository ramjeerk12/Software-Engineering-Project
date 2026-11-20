# Python Projects – Setup and Run Guide

This folder contains four independent Python projects. Each project has its own `app.py` file and should be run from its own project directory.

## Projects

- `delivery_agent_system`
- `Multimedia_Content_Protection_System_...`
- `Railway_Commodity_Reservation_System_...`
- `social_networking_p04`

> **Note:** The names of the second and third folders are shortened above because their full names are not visible in the folder screenshot. Use the exact folder names shown on your computer. In Windows Command Prompt or PowerShell, you can type the first few characters of a folder name and press **Tab** to complete it.

## Requirements

- Python installed on Windows
- A `requirements.txt` file inside the project directory

Check that Python is installed:

```bat
python --version
```

If that command does not work, install Python and make sure **Add Python to PATH** is selected during installation.

## Run any project

Open **Command Prompt** or **PowerShell** in the folder that contains all four project directories.

### 1. Move into the project directory

For example, to run the delivery agent project:

```bat
cd delivery_agent_system
```

For the other projects, use their exact folder names:

```bat
cd "Multimedia_Content_Protection_System_..."
```

```bat
cd "Railway_Commodity_Reservation_System_..."
```

```bat
cd social_networking_p04
```

If you are already inside a different project directory, return to the parent folder before entering another project:

```bat
cd ..
```

### 2. Create a virtual environment

Run this once for each project:

```bat
python -m venv venv
```

### 3. Activate the virtual environment

**Command Prompt:**

```bat
venv\Scripts\activate
```

**PowerShell:**

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use Command Prompt instead. Alternatively, for the current PowerShell session, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### 4. Install project dependencies

Make sure the project directory contains `requirements.txt`, then run:

```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Start the application

```bat
python app.py
```

If the application starts a local web server, the terminal will show a local address (often something like `http://127.0.0.1:5000`). Open the exact address printed in the terminal in your browser.

Keep the terminal open while using the application. To stop it, press **Ctrl + C**.

## Run another project

After stopping the current application:

1. Return to the parent folder:

   ```bat
   cd ..
   ```

2. Enter the next project directory:

   ```bat
   cd social_networking_p04
   ```

3. Activate that project's virtual environment:

   ```bat
   venv\Scripts\activate
   ```

4. Start the app:

   ```bat
   python app.py
   ```

Repeat the same process for the other project directories.

## Important notes

- Create a separate `venv` inside each project directory. Do not use one project's virtual environment for another project.
- Install dependencies separately in each project using that directory's `requirements.txt`.
- If `requirements.txt` is missing, check the project instructions or ask the project maintainer for the dependency list. The install command will not work without that file.
- If you see an error such as `No module named ...`, activate the correct project's virtual environment and install its requirements again.
- If `python` is not recognized, try `py` in place of `python` (for example, `py -m venv venv` and `py app.py`).

## Quick command summary

Run these commands from the parent folder, replacing the folder name with the project you want to start:

```bat
cd project_folder_name
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
