#!/usr/bin/python3

import sys
import os
import shutil
import tarfile
import logging
import subprocess
import time
import requests
import boto3
from botocore.errorfactory import ClientError
from google.cloud import storage

logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s", level=logging.INFO)

backupDir = "{{ mysql_backup_local_dir }}"
backupName = f"{time.strftime('%Y%m%d.%H%M')}.sql"
remoteStorage = "{{ mysql_backup_remote_storage }}"
bucketName = "{{ mysql_backup_bucket_name }}"
bucketDir = "{{ mysql_backup_bucket_dir }}"
useCompression = {{ mysql_backup_use_compression }}
deleteLocally = {{ mysql_backup_delete_locally }}
skipWhenDelete = {{ mysql_backup_skip_when_delete_locally }}
mysqlHost = "{{ mysql_backup_db_host }}"
mysqlUser = "{{ mysql_backup_db_user}}"
mysqlPassword = "{{ mysql_backup_db_password  }}"
mysqlDBName = "{{ mysql_backup_db_name }}"
telergamApiToken = "{{ mysql_backup_telergam_api_token }}"
telegramChatId = "{{ mysql_backup_telegram_chat_id }}"

if remoteStorage == "gcs":
    # Use GOOGLE_APPLICATION_CREDENTIALS env variable for GCP access
    gcs_client = storage.Client()

if remoteStorage == "s3":
    # Use AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_DEFAULT_REGION env variables for AWS access
    s3_client = boto3.client('s3')

def send_to_telegram(api_token,chat_id,message):
    if ( api_token and chat_id ):
        api_url = f"https://api.telegram.org/bot{api_token}/sendMessage"
        try:
            requests.post(api_url, json={"chat_id": chat_id, "text": message})
        except Exception as error:
            logging.error(f"Failed send message to telegram with error: {error}")

def create_mysql_backup(db_host,db_user,db_password,db_name,backup_name):
    cmd = f"mysqldump --no-tablespaces -h{db_host} -u{db_user} -p{db_password} {db_name} > {backup_name}"
    process = subprocess.run(cmd, shell=True)
    if process.returncode == 0:
        logging.info(f"Successfully created backup {backup_name}")
    else:
        logging.error(f"Backup {backup_name} creation failed with return code {process.returncode}")
        send_to_telegram(telergamApiToken, telegramChatId, "Mysql backup creation failed")
        sys.exit(1)

def check_remote_exists_s3(bucket_name, bucket_dir, backup_name):
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as error:
        if error.response['Error']['Code'] == "404":
            logging.error(f"The s3 bucket {bucket_name} does not exist")
            send_to_telegram(telergamApiToken, telegramChatId, f"The s3 bucket {bucket_name} does not exist. Skip upload")
        elif error.response['Error']['Code'] == "403":
            logging.error(f'AWS boto3 client unauthorized. {format(str(error))}')
        else:
            logging.error(f'Exception raised. {format(str(error))}')
    else:
        try:
            s3_client.head_object(Bucket=bucket_name, Key=f"{bucket_dir}/{backup_name}")
        except ClientError as error:
            if error.response['Error']['Code'] == "404":
                return False
            elif error.response['Error']['Code'] == "403":
                logging.error(f'AWS boto3 client unauthorized. {format(str(error))}')
            else:
                logging.error(f'Exception raised. {format(str(error))}')
        else:
            return True

def upload_to_s3(bucket_name, bucket_dir, backup_name):
    if os.path.isfile(backup_name):
        try: 
            s3_client.upload_file(backup_name, bucket_name, f"{bucket_dir}/{backup_name}")
            logging.info(f"Uploaded {backup_name} to s3://{bucket_name}/{bucket_dir}")
        except boto3.exceptions.S3UploadFailedError as error:
            logging.error(f"Failed upload {backup_name} to s3://{bucket_name}/{bucket_dir} with error: {format(str(error))}")
            send_to_telegram(telergamApiToken, telegramChatId, f"Failed upload {backup_name} to s3://{bucket_name}/{bucket_dir}")
    else:
        logging.info(f"Cant find {bucket_dir}/{backup_name} locally. Skip upload")

def check_remote_exists_gcs(bucket_name, bucket_dir, backup_name):
    try:
        bucket = gcs_client.bucket(bucket_name)
        if bucket.exists():
            stats = storage.Blob(bucket=bucket, name=f"{bucket_dir}/{backup_name}").exists(gcs_client)
            return stats
        else:
            logging.error(f"The gcs bucket {bucket_name} does not exist")
            send_to_telegram(telergamApiToken, telegramChatId, f"The gcs bucket {bucket_name} does not exist. Skip upload")
    except api_core.exceptions.Forbidden as error:
        logging.error(f'Permission denied. {format(str(error))}')
    except Exception as error:
        logging.error(f'Exception raised. {format(str(error))}')

def upload_to_gcs(bucket_name, bucket_dir, backup_name):
    bucket = gcs_client.bucket(bucket_name)
    if os.path.isfile(backup_name):
        try:
            blob = bucket.blob(f"{bucket_dir}/{backup_name}")
            blob.upload_from_filename(f"{backup_name}")
            logging.info(f"Uploaded {backup_name} to gs://{bucket_name}/{bucket_dir}")
        except Exception as error:
            logging.error(f"Failed upload {backup_name} to gs://{bucket_name}/{bucket_dir} with error: {format(str(error))}")
            send_to_telegram(telergamApiToken, telegramChatId, f"Failed upload {backup_name} to gs://{bucket_name}/{bucket_dir}")
    else:
        logging.info(f"Cant find {bucket_dir}/{backup_name} locally. Skip upload")

def make_tarball_and_compress(backup_name):
    with tarfile.open(f"{backup_name}.tar.gz", "w:gz") as tar:
        tar.add(f"{backup_name}", arcname=backup_name)
    logging.info(f"Created compressed tarball {backup_name}.tar.gz")

def delete_local_backup(backup_path):
    if os.path.isfile(backup_path):
        os.remove(backup_path)
        logging.info(f"Deleted {backup_path} locally")
    elif os.path.isdir(backup_path):
        shutil.rmtree(backup_path)
        logging.info(f"Deleted {backup_path} locally")
    else:
        logging.info(f"Cant find {backup_path} locally. Skip deletion")

def main():
    os.chdir(backupDir)
    create_mysql_backup(mysqlHost,mysqlUser,mysqlPassword,mysqlDBName,backupName)
    if useCompression:
        make_tarball_and_compress(backupName)
        delete_local_backup(backupName)
    for index, file in enumerate(sorted(os.listdir(backupDir), reverse=True, key=os.path.getmtime)):
        if remoteStorage == "gcs":
            if not check_remote_exists_gcs(bucketName, bucketDir, file):
                upload_to_gcs(bucketName, bucketDir, file)
        if remoteStorage == "s3":
            if not check_remote_exists_s3(bucketName, bucketDir, file):
                upload_to_s3(bucketName, bucketDir, file)
        if deleteLocally and index >= skipWhenDelete:
            delete_local_backup(file)


if __name__ == "__main__":
    main()