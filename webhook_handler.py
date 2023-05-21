#!/usr/bin/env python3

from script import run_script
from celery_app import app
import sys
import os
import json

# Main function that takes 3 arguments from the webhook and sends the result to the Celery task run_script
if __name__ == "__main__":
    """ Main function that takes 3 arguments from the whole payload 
        and sends the result to the celery task which is run_script
    
    """
    payload = json.loads(sys.argv[1])
    repo_name = payload['repository']['name']
    branch_name = payload['ref'].split('/')[-1]
    
    list_dvc_file_paths = []
    for commit in payload['commits']:
         if commit['added'] is not None:
            list_dvc_file_paths.extend(commit['added'])
    list_dvc_file_names = [os.path.basename(file) for file in list_dvc_file_paths if file.endswith('.xyz.dvc')]

    result = run_script.apply_async(args=(repo_name, branch_name, list_dvc_file_names), queue='script')
    print("Task submitted:", result.id)
    print(list_dvc_file_names)