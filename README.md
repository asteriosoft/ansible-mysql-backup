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
    clickhouse_backup_version: "2.4.35"
    clickhouse_backup_remote_storage: "s3"
    clickhouse_backup_user: "default"
    clickhouse_backup_password: ""
    clickhouse_backup_tables: "default.test"
    clickhouse_backup_port: 9000
    clickhouse_backup_bucket_name: "backups"
    clickhouse_backup_bucket_path: "clickhouse"
    clickhouse_backup_compression_level: 6
    clickhouse_backup_compression_format: "gzip"
    clickhouse_backup_concurrency: 2
    clickhouse_backup_api_enable: true
    clickhouse_backup_api_listener: "0.0.0.0:7171"
      
  roles:
    - clickhouse-backup
```

