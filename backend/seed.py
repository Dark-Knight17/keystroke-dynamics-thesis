import models
import database

def seed_tasks():
    db = database.SessionLocal()
    
    # Clear existing tasks and related data as per requirements
    print("Clearing existing data to avoid FK violations...")
    db.query(models.KeystrokeEvent).delete()
    db.query(models.Session).delete()
    db.query(models.ProgrammingTask).delete()
    db.commit()

    tasks_data = [
      {
        "task_title": "[Day 1] Transcription: Matrix Processing",
        "description": "DO NOT SOLVE. Re-type the following exactly, paying strict attention to indentation:\n\ndef process_data(matrix):\n    results = []\n    for i in range(len(matrix)):\n        for j in range(len(matrix[i])):\n            if matrix[i][j] % 2 == 0 and matrix[i][j] != 0:\n                results.append({'x': i, 'y': j, 'val': matrix[i][j]})\n    return results",
        "difficulty_level": "Medium",
        "expected_solution_length": 250
      },
      {
        "task_title": "[Day 1] Composition: String Reversal",
        "description": "Write a function `reverse_string(text)` that takes a string and returns it reversed. Do not use Python's slice trick `[::-1]`; use a `for` or `while` loop. This requires reasoning and variable declaration.",
        "difficulty_level": "Medium",
        "expected_solution_length": 200
      },
      {
        "task_title": "[Day 1] Syntax: Student Class",
        "description": "Create a class `Student`. Add an `__init__` method taking `self`, `name`, and `matric_number`. Add a method `get_details(self)` that returns an f-string with the student's information. Instantiate one student.",
        "difficulty_level": "Medium",
        "expected_solution_length": 200
      },
      {
        "task_title": "[Day 1] Debugging: Infinite Loop",
        "description": "Type the CORRECTED version of this code. Fix the infinite loop and indentation errors:\n\ndef print_numbers(max_val):\ncount = 0\n  while count < max_val\n    print(count)\n     count - 1",
        "difficulty_level": "Medium",
        "expected_solution_length": 150
      },
      {
        "task_title": "[Day 2] Transcription: API Request",
        "description": "DO NOT SOLVE. Re-type the following exactly:\n\nimport requests\n\ndef fetch_user(user_id):\n    try:\n        response = requests.get(f'https://api.test.com/v1/users/{user_id}')\n        response.raise_for_status()\n        return response.json().get('profile')\n    except requests.exceptions.RequestException as e:\n        print(f'API Error: {e}')",
        "difficulty_level": "Medium",
        "expected_solution_length": 250
      },
      {
        "task_title": "[Day 2] Composition: Palindrome Checker",
        "description": "Write a function `is_palindrome(word)` that returns True if the word reads the same forwards and backwards. Handle edge cases like empty strings. Use standard control flow.",
        "difficulty_level": "Medium",
        "expected_solution_length": 200
      },
      {
        "task_title": "[Day 2] Syntax: List Comprehension",
        "description": "Given a list of dictionaries `data = [{'id': 1, 'score': 40}, {'id': 2, 'score': 80}]`, write a function that uses a list comprehension to return only the `id` of items where the `score` is 50 or higher.",
        "difficulty_level": "Medium",
        "expected_solution_length": 200
      },
      {
        "task_title": "[Day 2] Debugging: Broken Logic",
        "description": "Type the CORRECTED version. Fix the missing colons, typos, and `elif` structure:\n\ndef check_status(status)\n    if status == 'ACTIVE'\n        return 1\n    else if status == 'PENDING':\n        return 0\n    else\n        return -1",
        "difficulty_level": "Medium",
        "expected_solution_length": 150
      },
      {
        "task_title": "[Day 3] Transcription: Dictionary Grouping",
        "description": "DO NOT SOLVE. Re-type the following exactly:\n\ndef group_by_role(users):\n    grouped = {}\n    for user in users:\n        role = user.get('role', 'guest')\n        if role not in grouped:\n            grouped[role] = []\n        grouped[role].append(user['name'])\n    return grouped",
        "difficulty_level": "Medium",
        "expected_solution_length": 250
      },
      {
        "task_title": "[Day 3] Composition: Array Max Number",
        "description": "Write a function `find_max(numbers)` that iterates through a list of numbers and returns the largest integer. Do not use the built-in `max()` function.",
        "difficulty_level": "Medium",
        "expected_solution_length": 200
      },
      {
        "task_title": "[Day 3] Syntax: Try/Except File I/O",
        "description": "Write a `try...except` block that attempts to open a file named 'data.txt' in read mode ('r'). In the `except FileNotFoundError` block, print the error message using an f-string.",
        "difficulty_level": "Easy",
        "expected_solution_length": 150
      },
      {
        "task_title": "[Day 3] Debugging: OOP Inheritance",
        "description": "Type the CORRECTED version. Fix the class inheritance and `super()` call:\n\nclass Admin(User):\n    def __init__(self, name, role):\n        super().init(name)\n        self.role = role\n\n    def get_role():\n        return self.role",
        "difficulty_level": "Medium",
        "expected_solution_length": 150
      }
    ]

    tasks = [models.ProgrammingTask(**task_data) for task_data in tasks_data]

    db.add_all(tasks)
    db.commit()
    print(f"Successfully seeded {len(tasks)} tasks.")
    db.close()

if __name__ == "__main__":
    # Ensure tables exist
    models.Base.metadata.create_all(bind=database.engine)
    seed_tasks()
