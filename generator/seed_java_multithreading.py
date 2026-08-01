import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from app.database import init_db, ensure_beanie_initialized
from app.models.question import Question, Option

questions_data = [
    {
        "topic": "Java",
        "subtopic": "Multithreading",
        "question_text": "Which of the following is the most recommended way to define a task for execution by a thread pool in Java?",
        "options": [
            {"index": 0, "text": "Inheriting from the Thread class."},
            {"index": 1, "text": "Implementing the Runnable or Callable interface."},
            {"index": 2, "text": "Implementing the Task interface."},
            {"index": 3, "text": "Instantiating the ThreadGroup class."}
        ],
        "correct_option_indices": [1],
        "explanation": "Implementing Runnable or Callable is preferred over extending Thread because it promotes better separation of concerns, allows task reuse, and doesn't consume the single inheritance limit in Java.",
        "difficulty": "EASY"
    },
    {
        "topic": "Java",
        "subtopic": "Multithreading",
        "question_text": "What guarantee does the volatile keyword provide in Java?",
        "options": [
            {"index": 0, "text": "It ensures both atomicity of compound operations and visibility of variable updates across threads."},
            {"index": 1, "text": "It prevents execution of concurrent read operations."},
            {"index": 2, "text": "It guarantees that reads and writes of the variable are written directly to and read from main memory, ensuring visibility, but does not guarantee atomicity of compound operations."},
            {"index": 3, "text": "It locks the object instance, preventing other threads from calling methods on it."}
        ],
        "correct_option_indices": [2],
        "explanation": "The volatile keyword guarantees visibility (changes made by one thread to the shared variable are visible to other threads immediately) and prevents instruction reordering, but it does not guarantee atomicity for compound operations (like count++).",
        "difficulty": "MEDIUM"
    },
    {
        "topic": "Java",
        "subtopic": "Multithreading",
        "question_text": "What does a thread lock when entering a non-static synchronized method?",
        "options": [
            {"index": 0, "text": "The Class object associated with the instance."},
            {"index": 1, "text": "The specific instance of the object (this) on which the method is called."},
            {"index": 2, "text": "The entire JVM memory space."},
            {"index": 3, "text": "Only the variables modified inside the method."}
        ],
        "correct_option_indices": [1],
        "explanation": "A non-static synchronized method locks the monitor of the 'this' object instance. If it were static, it would lock the Class object.",
        "difficulty": "EASY"
    },
    {
        "topic": "Java",
        "subtopic": "Multithreading",
        "question_text": "If a thread is waiting to acquire an object lock that is currently held by another thread, what state is it in?",
        "options": [
            {"index": 0, "text": "WAITING"},
            {"index": 1, "text": "TIMED_WAITING"},
            {"index": 2, "text": "BLOCKED"},
            {"index": 3, "text": "RUNNABLE"}
        ],
        "correct_option_indices": [2],
        "explanation": "A thread is in the BLOCKED state when it is waiting for a monitor lock to enter a synchronized block or method. WAITING state is when it waits for another thread to perform a specific action (like Object.wait() or Thread.join()).",
        "difficulty": "MEDIUM"
    },
    {
        "topic": "Java",
        "subtopic": "Multithreading",
        "question_text": "Which of the following conditions is NOT required for a deadlock to occur in a concurrent application?",
        "options": [
            {"index": 0, "text": "Mutual exclusion"},
            {"index": 1, "text": "Hold and wait"},
            {"index": 2, "text": "No preemption"},
            {"index": 3, "text": "Starvation"}
        ],
        "correct_option_indices": [3],
        "explanation": "Coffman conditions for deadlock are: Mutual exclusion, Hold and wait, No preemption, and Circular wait. Starvation is a symptom of scheduling/locking issues but is not a necessary condition for deadlock.",
        "difficulty": "MEDIUM"
    },
    {
        "topic": "Java",
        "subtopic": "Multithreading",
        "question_text": "What is the main difference between shutdown() and shutdownNow() methods on an ExecutorService?",
        "options": [
            {"index": 0, "text": "shutdown() stops all executing tasks immediately, whereas shutdownNow() allows currently running tasks to finish."},
            {"index": 1, "text": "shutdown() prevents new tasks from being submitted but allows existing queued and running tasks to complete; shutdownNow() attempts to stop actively executing tasks (using thread interruption) and returns a list of waiting tasks."},
            {"index": 2, "text": "shutdown() deletes the thread pool, whereas shutdownNow() puts threads to sleep."},
            {"index": 3, "text": "There is no difference; they are aliases of each other."}
        ],
        "correct_option_indices": [1],
        "explanation": "shutdown() initiates an orderly shutdown (no new tasks, completes existing ones). shutdownNow() attempts to halt running tasks using thread interrupts and returns tasks that were queued but never started.",
        "difficulty": "MEDIUM"
    },
    {
        "topic": "Java",
        "subtopic": "Multithreading",
        "question_text": "Which of the following best describes the purpose of ThreadLocal in Java?",
        "options": [
            {"index": 0, "text": "To share a single variable instance safely among all threads using a global lock."},
            {"index": 1, "text": "To provide thread-local variables where each thread has its own, independently initialized copy of the variable."},
            {"index": 2, "text": "To synchronize block execution across distributed JVM nodes."},
            {"index": 3, "text": "To speed up thread creation by caching threads in a local pool."}
        ],
        "correct_option_indices": [1],
        "explanation": "ThreadLocal provides variables that are locally isolated to a thread, meaning each thread accessing the variable gets its own independently initialized instance, avoiding synchronization overhead.",
        "difficulty": "MEDIUM"
    },
    {
        "topic": "Java",
        "subtopic": "Multithreading",
        "question_text": "What mechanism does ForkJoinPool use to optimize execution of tasks where threads can steal tasks from other busy threads?",
        "options": [
            {"index": 0, "text": "Work-stealing algorithm"},
            {"index": 1, "text": "Round-robin scheduling"},
            {"index": 2, "text": "Mutex prioritization"},
            {"index": 3, "text": "Priority task preemption"}
        ],
        "correct_option_indices": [0],
        "explanation": "ForkJoinPool uses a work-stealing algorithm, where idle threads steal tasks from the deques of other threads that are still busy, maximizing CPU core utilization.",
        "difficulty": "HARD"
    },
    {
        "topic": "Java",
        "subtopic": "Multithreading",
        "question_text": "Which method in CompletableFuture would you use to chain a callback that consumes the result of the previous stage and returns a new CompletableFuture?",
        "options": [
            {"index": 0, "text": "thenAccept"},
            {"index": 1, "text": "thenApply"},
            {"index": 2, "text": "thenCompose"},
            {"index": 3, "text": "thenRun"}
        ],
        "correct_option_indices": [2],
        "explanation": "thenCompose is used for monadic chaining (similar to flatMap) when the callback returns another completion stage. thenApply is used when the callback returns a plain value (similar to map).",
        "difficulty": "HARD"
    },
    {
        "topic": "Java",
        "subtopic": "Multithreading",
        "question_text": "What is a primary difference between CountDownLatch and CyclicBarrier in Java concurrency?",
        "options": [
            {"index": 0, "text": "A CountDownLatch can be reset and reused after its count reaches zero, whereas a CyclicBarrier cannot."},
            {"index": 1, "text": "A CyclicBarrier can be reset and reused after the barrier is tripped, whereas a CountDownLatch cannot be reused."},
            {"index": 2, "text": "CountDownLatch is used for coordinating threads across multiple JVM instances, while CyclicBarrier is for a single JVM."},
            {"index": 3, "text": "A CyclicBarrier only blocks the main thread, while a CountDownLatch blocks worker threads."}
        ],
        "correct_option_indices": [1],
        "explanation": "CyclicBarrier can be reused after the waiting threads are released, which is why it is called 'cyclic'. CountDownLatch count cannot be reset; once it reaches zero, it cannot be used again.",
        "difficulty": "HARD"
    }
]

async def main():
    client = await init_db()
    await ensure_beanie_initialized(client)
    try:
        documents = []
        for q in questions_data:
            options = [Option(index=opt["index"], text=opt["text"]) for opt in q["options"]]
            doc = Question(
                topic=q["topic"],
                subtopic=q["subtopic"],
                question_text=q["question_text"],
                options=options,
                correct_option_indices=q["correct_option_indices"],
                explanation=q["explanation"],
                difficulty=q["difficulty"]
            )
            documents.append(doc)
            
        result = await Question.insert_many(documents)
        print(f"Successfully inserted {len(result.inserted_ids)} questions into database.")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(main())
