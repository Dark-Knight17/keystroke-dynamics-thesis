from database import SessionLocal
from models import ProgrammingTask

def apply_live_hotfix():
    db = SessionLocal()
    
    print("Initiating live database hotfix...")
    
    # Find all Transcription tasks
    transcription_tasks = db.query(ProgrammingTask).filter(
        ProgrammingTask.task_title.like("%Transcription%")
    ).all()
    
    for task in transcription_tasks:
        old_val = task.expected_solution_length
        task.expected_solution_length = 180
        print(f"Updated '{task.task_title}': {old_val} -> 180")
        
    db.commit()
    db.close()
    print("Hotfix complete. No user data was harmed!")

if __name__ == "__main__":
    apply_live_hotfix()