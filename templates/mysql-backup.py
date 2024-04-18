#!/usr/bin/python3

from google.cloud import storage
import os
import shutil
import glob
import tarfile
import logging
import subprocess
import time
import requests

logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s", level=logging.INFO)

backupDir = "{{ mysql_backup_local_dir }}"
backupName = f"{time.strftime('%Y%m%d.%H%M')}.sql"
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

storage_client = storage.Client()

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

def check_remote_exists(bucket_name, bucket_dir, backup_name):
    bucket = storage_client.bucket(bucket_name)
    stats = storage.Blob(bucket=bucket, name=f"{bucket_dir}/{backup_name}").exists(storage_client)
    return stats

def upload_to_gcs(bucket_name, bucket_dir, backup_name):
    bucket = storage_client.bucket(bucket_name)
    if os.path.isfile(backup_name):
        try:
            blob = bucket.blob(f"{bucket_dir}/{backup_name}")
            blob.upload_from_filename(f"{backup_name}")
            logging.info(f"Uploaded {backup_name} to gs://{bucket_name}/{bucket_dir}")
        except Exception as error:
            logging.error(f"Failed upload {backup_name} to gs://{bucket_name}/{bucket_dir} with error: {error}")
            send_to_telegram(telergamApiToken, telegramChatId, f"Failed upload {backup_name} to gs://{bucket_name}/{bucket_dir}")
    elif os.path.isdir(backup_name):
        try:
            for str_path_file in glob.glob(f"{backup_name}/**/*", recursive=True):
                if os.path.isfile(str_path_file):
                    blob = bucket.blob(f"{bucket_dir}/{str_path_file}")
                    blob.upload_from_filename(str_path_file)
            logging.info(f"Uploaded {backup_name} to gs://{bucket_name}/{bucket_dir}")
        except Exception as error:
            logging.error(f"Failed upload {backup_name} to gs://{bucket_name}/{bucket_dir} with error: {error}")
            send_to_telegram(telergamApiToken, telegramChatId, f"Failed upload {backup_name} to gs://{bucket_name}/{bucket_dir}")
    else:
        logging.info(f"Cant find {backup_name} locally. Skip upload")

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
    for index, backup in enumerate(sorted(os.listdir(backupDir), reverse=True, key=os.path.getmtime)):
        if not check_remote_exists(bucketName, bucketDir, backup):
            upload_to_gcs(bucketName, bucketDir, backup)
        if deleteLocally and index >= skipWhenDelete:
            delete_local_backup(backup)


if __name__ == "__main__":
    main()