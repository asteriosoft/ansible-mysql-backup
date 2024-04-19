Mysql-backup
=========

Role for scheduled mysql DB backups

Role Variables
--------------

To do

Example Playbook
----------------
```
- hosts: servers
  become: yes
  gather_facts: yes

  vars:
    mysql_backup_db_host: "localhost"
    mysql_backup_db_user: "backup_user"
    mysql_backup_db_password: "backup_password"
    mysql_backup_db_name: "test"
    mysql_backup_local_dir: "/root/mysql-backup"
    mysql_backup_use_compression: true
    mysql_backup_delete_locally: true
    mysql_backup_skip_when_delete_locally: 5
    mysql_backup_remote_storage: "s3"
    mysql_backup_bucket_name: "backups"
    mysql_backup_bucket_dir: "mysql"
      
  roles:
    - mysql-backup
```

