#!/usr/bin/env python3

from __future__ import absolute_import, unicode_literals
from celery_app import app
import redis
import os
import subprocess
import sys
import time
import shutil
import fcntl
import glob
import sentry_sdk
import re
import queue
import threading
import tempfile
from pathlib import Path
import multiprocessing as mp
from sentry_sdk import capture_exception
from os.path import splitext, basename
from contextlib import contextmanager


geo_path = '/home/vsaintloui/valmy/geometries/'
energy_path='/home/vsaintloui/valmy/energies/'
gs_energy_path ='/home/vsaintloui/valmy/gs_energies/'
run_time_path = '/home/vsaintloui/valmy/gs_energies/'
orca_path= '/opt/orca_5_0_3_linux_x86-64_openmpi411/orca'
lock_file = open('/home/vsaintloui/valmy/repo/script/separate-file.lock', 'w')
output_repo= '/home/vsaintloui/valmy/workrepo/molecule_repo/benzene/cmd/properties/'
geo_path_repo ='/home/vsaintloui/valmy/workrepo/molecule_repo/benzene/cmd/geometries/'
sentry_sdk.init('https://34bf612982af41c89dde38029a16861e@o4505107939393536.ingest.sentry.io/4505107943653376')


# Function to separate file into individual molecule strings
def separate_trajectory(input_file, output_directory, prefix):
    """ Function to separate file into individual molecule strings
    
        Parameters:

        input_file (str): path of the trajectory file
        output_directory(str): path of saved geometries files from trajectory
        prefix(str): name of the file here it's 'geometry'
    
    """

    # check if path is a file
    isFile = os.path.isfile(input_file)
    print(isFile)

    if isFile:
        with open(input_file,'r') as f:
            contents =f.read()
    else:
        files=list(Path(input_file).rglob('*.xyz'))
        if not files:
            print("No .xyz files found in the specified directory")
        else:
            file_path=files[0].as_posix()
            with open(file_path,'r') as f:
                contents =f.read()


    # Split the contents into individual lines
    lines = contents.strip().split('\n')

    # Initialize an empty list to hold the individual molecule strings
    molecules = []

    for i, line in enumerate(lines):
        if not line.strip().isdigit():
            continue

        num_atoms = int(line)
        molecule_str = '\n'.join(lines[i:i + num_atoms + 2]) + '\n'
        molecules.append(molecule_str)

    # Create the output directory if it doesn't already exist
    os.makedirs(output_directory, exist_ok=True)

    # Loop over each molecule and write it to a separate file in the output directory
    for i, molecule in enumerate(molecules):
        # Construct the output file name for the current molecule
        output_file = os.path.join(output_directory, f'{prefix}_{i+1}.xyz')

        # Write the current molecule to the output file
        with open(output_file, 'w') as f:
            f.write(molecule)

# Function to calculate energy
def calculate_energy(input_file, output_directory, file_name, energy_calculation_method):
    """ Function to calculate excited energy and ground state energy

        Adapt Phd Student's code originally written in Shell of 
        Holzenkamp Matthias at Constructor University to Python language

        Parameters:

        input_file(str): path of saved geometries files from trajectory
        output_directory(str): path of files generated after calculating  energy
        file_name(str): name of the current trajectory processing
        energy_calculation_method(str): name of the computational chemistry method to run Orca
    
    """
    input_file_str = str(input_file)
    # Create the output directory if it doesn't already exist
    os.makedirs(output_directory, exist_ok=True)
    os.makedirs(gs_energy_path, exist_ok =True)
    os.chdir(output_directory)
    file_basename = splitext(basename(file_name))[0]
    
    with open(f'/home/vsaintloui/valmy/template/{energy_calculation_method}') as orca_template:
        template_contents = orca_template.read()


    for filename in sorted(os.listdir(input_file_str)):
        if filename.endswith('.xyz'):
            filepath = input_file_str + '/' + filename
            input_filename = splitext(filename)[0] + '.inp'
            
            # Create orca input file
            input_contents = template_contents + f'\n *xyzfile 0 1 {filepath}\n'
            with open(input_filename, 'w') as input_file:
                input_file.write(input_contents)

            # Run orca on input file
            log_filename = splitext(filename)[0] + '.log'
            orca_command = f"{orca_path} {input_filename} > {log_filename}"
            try:
                subprocess.run(orca_command, shell=True, check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error running Orca command: {e.cmd}")
                print(f"Return code: {e.returncode}")
                print(f"Output: {e.output}")
                print(f"Error output: {e.stderr}")

            energy_filename = os.path.join(energy_path, energy_calculation_method + '.dat')
            gs_energy_filename = os.path.join(gs_energy_path, energy_calculation_method + '.dat')
                

            energy_data = []
            gs_energy_data = []

            with open(log_filename) as log_file:
                found_lowest_energy = found_e_scf = False
                for line in log_file:
                    if not found_lowest_energy and 'Lowest Energy' in line:
                        energy = line.split()[3]
                        float_energy = float(energy) * 27.211386245988
                        energy_data.append(str(float_energy))
                        found_lowest_energy = True
                        
                    if not found_e_scf and "E(SCF)" in line:
                        gs_energy_value = line.split()[2]
                        float_gs_energy = float(gs_energy_value) * 27.211386245988
                        gs_energy_data.append(str(float_gs_energy))
                        found_e_scf = True

                    if found_lowest_energy and found_e_scf:
                        break

            with open(energy_filename, 'a') as energy_file, \
                    open(gs_energy_filename, 'a') as gs_energy_file:
                    energy_file.write('\n'.join(energy_data) + '\n')
                    gs_energy_file.write('\n'.join(gs_energy_data) + '\n')

            extract_run_time(file_basename, log_filename, energy_calculation_method)

            
# Function to extract run time to calculate the energy
def extract_run_time(filename,log_file_path, energy_calculation_method):

    data_file_path = os.path.join(output_repo,filename,'run_time',f'{energy_calculation_method}.dat')
    dir_path = os.path.dirname(data_file_path)
    os.makedirs(dir_path, exist_ok = True)

    run_time_pattern =  re.compile(r"TOTAL RUN TIME:\s+\d+ days\s+(\d+) hours\s+(\d+) minutes\s+(\d+) seconds\s+(\d+) msec")

    with open(log_file_path, 'r') as log_file:
         for line in log_file:
            match = run_time_pattern.search(line)
            if match:
                hours, minutes, seconds, mseconds = match.groups()
                total_seconds = float(hours) * 3600 + float(minutes) * 60 + float(seconds) + float(mseconds)/1000
                total_seconds=total_seconds/60
                break
    with open(data_file_path, 'a') as data_file:
            data_file.write(f'{total_seconds:.6f}\n')

# Function to prepend energy 
def prepend_data(filename, data_type, energy_calculation_method):
    data_type_map = {
        "energy": (energy_path, "es_energies"),
        "gs_energy": (gs_energy_path, "gs_energies")
    }

    if data_type not in data_type_map:
        raise ValueError(f"Invalid data_type: {data_type}")

    input_path, subdir = data_type_map[data_type]
    input_file = f"{input_path}/{energy_calculation_method}.dat"

    file_basename = splitext(basename(filename))[0]
    output_file = f"{output_repo}/{file_basename}/{subdir}/{energy_calculation_method}.dat"

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(input_file, 'r') as f_in, open(output_file, 'w') as f_out:
        for i, line in enumerate(f_in):
            row = line.rstrip('\n').split('\t')
            row.insert(0, str(i))
            f_out.write('\t'.join(row) + '\n')
    shutil.move(output_file, input_file)
    shutil.move(input_file, output_file)

# Function to remove specific files generated by Orca
def remove_extension():
    # Remove all files with the specified extensions
    for ext in ['xyz', 'dvc', 'gbw', 'cis', 'prop', 'txt']:
        for file in glob.glob(f'*.{ext}'):
            os.remove(file)

# Function to delete files in geometries folder
def delete_contents_geometries(directory_path, extensions, basenames):
    if not os.path.exists(directory_path):
        raise Exception(f"The directory {directory_path} does not exist")

    deleted_files = False
    for basename in basenames:
        for ext in extensions:
            if ext == 'xyz':
                patterns = [f"{directory_path}/**/{basename}.{ext}", f"{directory_path}/**/{basename}.{ext}.*"]
            for pattern in patterns:
                files = glob.glob(pattern, recursive=True)
                print(f"Found {len(files)} files with pattern {pattern}")
                for file_path in files:
                    try:                        
                        os.remove(file_path)
                        deleted_files = True
                    except Exception as e:
                        print(f"Failed to delete {file_path}. Reason: {str(e)}")

    if not deleted_files:
        print(f"No files with basenames {basenames} and extensions {extensions} were found in {directory_path}")



# Function to delete properties folder
def delete_contents_properties(directory_path):
    try:
        if not os.path.isdir(directory_path):
            raise Exception(f"The directory {directory_path} does not exist or is not a directory")
        
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            if os.path.isfile(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
    except Exception as e:
        raise Exception(f'Failed to delete contents of {directory_path}. Reason: {e}')
        
# Function to delete properties and geometries
def delete_local_files(directory_path, directory_to_delete_path, extensions,basenames):
    delete_contents_geometries(directory_path, extensions, basenames)
    delete_contents_properties(directory_to_delete_path)

  # Function to push using git
def git_push(remote, branch_name):
    try:
        output = subprocess.check_output(['git', 'push', remote, branch_name], stderr=subprocess.STDOUT)
        print("Push succeeded.")
    except subprocess.CalledProcessError as e:
        output = e.output.decode('utf-8')
        if "failed to update ref" in output:
            print("Push failed. Pulling latest changes from remote repository.")
            subprocess.call(['git', 'pull', remote, branch_name, '--no-edit'])
            print("Retrying push.")
            git_push(remote, branch_name)
        if "failed to push" in output:
            subprocess.call(['git', 'pull', remote, branch_name, '--no-edit']) # Skip interactive editor and enter a generic merging commit statement
            print("Retrying push.")
            git_push(remote, branch_name)
  
            
# Function to push data to Gitea repostiroy and Azure cloud storage
def push_data_to_repo(directory,filename, energy_calculation_method, branch_name):
#     os.chdir('/home/vsaintloui/valmy/workrepo/molecule_repo')
    os.chdir(directory)
    remote = subprocess.check_output(['git', 'remote']).decode('utf-8').strip()

    # Remove the file extension and only keep the filename
    file_basename = splitext(basename(filename))[0]

    output_file = f"{output_repo}/{file_basename}/es_energies/{energy_calculation_method}.dat"
    output_file_gs = f"{output_repo}/{file_basename}/gs_energies/{energy_calculation_method}.dat"
    output_file_run_time = f"{output_repo}/{file_basename}/run_time/{energy_calculation_method}.dat"

    # Run the 'dvc add' command
    add_data=subprocess.check_output(['dvc', 'add', output_file, output_file_gs, output_file_run_time], universal_newlines=True)
    print('newline :', add_data)
    # Run the 'git commit' command
    commit= subprocess.check_output(['git', 'commit', '-m', 'adding new data'], universal_newlines=True)
    print('output :', commit)
    git_push(remote, branch_name)

geo_path_repo ='/home/vsaintloui/valmy/workrepo/molecule_repo/benzene/cmd/geometries/'


def clear_cache_and_fetch_data():
#     subprocess.run(['dvc', 'gc', '-c'], check=True)
    subprocess.run(['dvc', 'fetch', '-a', '-T'], check=True)


def run_git_checkout(branch_name):

    """ Function to checkout the current branch, in case if fail, fetch the data 

        Parameter : 
        
        branch_name (str)

    """
    try:
        subprocess.run(['git', 'checkout', branch_name], check=True)
    except subprocess.CalledProcessError as e:
            print(f'Error during git checkout: {e}')

            try:
                clear_cache_and_fetch_data()
                # Attempt git checkout again after clearing cache and fetching data
                subprocess.run(['git', 'checkout', branch_name], check=True)
            except Exception as e:
                print(f'Error during cache clearing and data fetching: {e}')
                capture_exception(e)
        
# Function to get the last files committed using dvc pull
def get_last_dvc_pulled_files(directory, branch_name, list_dvc_file_names):
    
    """ Function to get the last files that was committed using DVC
    
        Parameters :
        
        directory (str): 
        branch_name(str):
        list_dvc_file_names(list):
        
        Return :
        
        list: 
    """
    os.chdir(directory)
    
    git_pull_result=subprocess.run(['git', 'pull', 'origin', 'main'], check=True, stdout=subprocess.PIPE)  
    print(git_pull_result.stdout.decode('utf-8'))
    cmd = ['dvc', 'pull'] + [geo_path_repo + ele for ele in list_dvc_file_names]

    result = subprocess.check_output(cmd, universal_newlines=True)
    print(result)
    run_git_checkout(branch_name) 
    lines = result.split('\n')
    file_lines = [line for line in lines if line.startswith('A       ')]
    files = [line.split('A       ')[1] for line in file_lines]
    xyz_files = []
    for file in files:
        file_path = os.path.join(directory, file)
        if os.path.isdir(file_path):
            xyz_files.extend(get_xyz_files_from_folder(file_path))
        elif file.endswith('.xyz'):
            xyz_files.append(file_path)
    return xyz_files


# Function to make sure get file with xyz extension inside of a folder
def get_xyz_files_from_folder(folder_path):
    xyz_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.xyz'):
                xyz_files.append(os.path.join(root, file))
    return xyz_files

# Function to call all other functions
def process_file(directory, filename, energy_calculation_method,branch_name):
    file_basename = basename(filename)
    print(f'\nProcessing file: {file_basename}')
    latest_file = os.path.join(directory, filename)
    if latest_file:
        print('found file ', latest_file)
        separate_trajectory(latest_file, geo_path, 'geometry')
        calculate_energy(geo_path, energy_path, filename, energy_calculation_method)
        prepend_data(filename, "energy",energy_calculation_method)
        prepend_data(filename, "gs_energy",energy_calculation_method)
        remove_extension()
        shutil.rmtree(geo_path)
        shutil.rmtree(energy_path)
        push_data_to_repo(directory,filename,energy_calculation_method, branch_name)

    else:
        print('No file found')

def handle_push_events(directory, files, energy_calculation_method, branch_name):
    """ """
    if len(files) == 0:
        print('No files to process')
        return
    num_processes = mp.cpu_count() - 1
    pool = mp.Pool(processes=num_processes)
    results = [pool.apply(process_file, args=(directory, filename,energy_calculation_method, branch_name)) for filename in files]
    pool.close()
    pool.join()
    print(f'\nAll files processed')


def handle_webhook_event(repo_name, branch_name, list_dvc_file_names):
        directory = f"/home/vsaintloui/valmy/workrepo/{repo_name}"
        files_to_process = get_last_dvc_pulled_files(directory, branch_name, list_dvc_file_names)

        if len(files_to_process) == 0:
            print('No files found')
        else:
            directory = os.path.dirname(files_to_process[0])
            print(f'Number of files to process: {len(files_to_process)}\n')
            start_time = time.time()

            template_files = glob.glob('/home/vsaintloui/valmy/template/*')
            for input_file_path in template_files:
                input_file_basename = splitext(basename(input_file_path))[0]
                try:
                    print('Before handle_push_events')  
                    handle_push_events(directory, files_to_process, input_file_basename,branch_name)
                    print('After handle_push_events')  
                except Exception as e:
                    print(f'Exception occurred: {e}')
                    capture_exception(e)

            directory_to_delete = f"{output_repo}"
            basenames = [os.path.splitext(os.path.splitext(name)[0])[0] for name in list_dvc_file_names] 
            delete_local_files(directory, directory_to_delete, ['xyz', 'dvc'], basenames)
            end_time = time.time()
            print(f'Total time taken: {end_time - start_time} seconds')


REDIS_CLIENT = redis.Redis()
@contextmanager
def redis_lock(lock_name):
    """ Jozo (2012). Celery task schedule: Ensuring a task is only executed one at a time. Retrieved from
        https://stackoverflow.com/questions/12003221/celery-task-schedule-ensuring-a-task-is-only-executed-one-at-a-time.
        
        Yield 1 if specified lock_name is not already set in redis. Otherwise returns 0.
        Enables sort of lock functionality.
    
        Parameters : 
    
        lock_name (str): name choosen for the lock in string 
    
    """
    status = REDIS_CLIENT.set(lock_name, 'lock', nx=True)
    try:
        yield status
    finally:
        REDIS_CLIENT.delete(lock_name)


@app.task(bind=True)
# Function that call handle_webhook_event() function
def run_script(self, repo_name, branch_name, list_dvc_file_names):
        with redis_lock('lock_key_777') as acquired:
            handle_webhook_event(repo_name, branch_name, list_dvc_file_names)
            


   
