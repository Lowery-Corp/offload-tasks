crud-endpoint: https://dscrapyard.johnmgrubbs.io/docs
auth-endpoint: https://auth.johnmgrubbs.io/docs


Get the authtoken from the auth-endpoint and use it to authenticate the request to the crud-endpoint.
Then, update the task to return the retrieved jobs in the response.

TASK: Update the worker task @celery_app.task(name="tasks.file_tasks.process_document")
    to retrieve the jobs from the database using the crud-endpoint.

Step 1:
    Create a function that gets the authtoken from the auth-endpoint. This function should make a request to the auth-endpoint with the necessary credentials and return the authtoken.

Step 2:
    Create a function that retrieves the jobs from the crud-endpoint. This function should take the authtoken as an argument and make a request to the crud-endpoint to retrieve the jobs. The function should return the retrieved jobs.

