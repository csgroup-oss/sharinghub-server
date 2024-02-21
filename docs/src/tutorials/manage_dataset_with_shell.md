# Manage large dataset with shell

## Introduction

You can upload project-related data directly to SharingHub without going through Git.
This can be used to manage large volumes of data, or to benefit from faster data access thanks to SharingHub.
The advantage of using SharingHub over an external storage system is that the access rights of the GIT project to which the GIT project is linked are preserved. It is therefore impossible for a third-party user who does not have access to the Git project to gain access to this data.

## Using `curl`

Curl can be a simple, all-purpose solution for managing the data lifecycle.
A GitLab token is required, as well as a project number to which the data can be assigned.

To upload a file with curl.

Using PUT:

```shell
curl -L -d @<file_to_upload> -X PUT -H 'Content-Type:application/octet-stream' -H 'X-Gitlab-Token:<your_gitlab_token>' https://sharinghub.p2.csgroup.space/store/<project_id>/<complete_file_path>

# or

curl -L -T <file_to_upload> -X PUT -H 'Content-Type:application/octet-stream' -H 'X-Gitlab-Token:<your_gitlab_token>' https://sharinghub.p2.csgroup.space/store/<project_id>/<complete_file_path>
```

Using POST:
> Please note that the PUT function can be several times faster than the POST method.

```shell
curl -d @<file_to_upload> -H 'X-Gitlab-Token:<your_gitlab_token>' https://sharinghub.p2.csgroup.space/store/<project_id>/
```

To access the data:

```shell
curl -L -H 'X-Gitlab-Token:toto' http://localhost:19422/store/1243/README.md
```

## Using `upload_to_sharinghub.sh`

To facilitate the upload of complex tree structures, the "upload_to_sharinghub.sh" script has been created. It makes it very easy to upload a directory and its sub-folders to SharingHub.

```shell
upload_to_sharinghub.sh <dir_path_to_upload> <project_id>
```

upload_to_sharinghub.sh:

```shell
#!/bin/bash

urlencode() {
  # urlencode <string>
  old_lc_collate=$LC_COLLATE
  LC_COLLATE=C

  local length="${#1}"
  for (( i = 0; i < length; i++ )); do
    local c="${1:i:1}"
    case $c in
      [a-zA-Z0-9.~_-]) printf '%s' "$c" ;;
      *) printf '%%%02X' "'$c" ;;
    esac
  done

  LC_COLLATE=$old_lc_collate
}

# Check if the number of arguments is correct
if [ $# -lt 2 ]
then
    echo "Usage: $0 <dir_path> <project_id>"
    exit 1
fi

if [ -z "$GITLAB_TOKEN" ]
then
  echo "The environment variable GITLAB_TOKEN must be set with a valid GitLab token."
  exit 1
fi

# Set the directory path to be uploaded
dir_path="$1"

# Set the GitLab project ID
project_id="$2"

sub_path="${3:-data}"

# Set the server URL
server_url="https://sharinghub.p2.csgroup.space/store/$project_id/$sub_path"

# Loop through all files and directories in the specified directory
for file in "$dir_path"/*
do
    # Check if the current item is a file
    if [ -f "$file" ]
    then
        # Upload the file to the server using curl
        if [ -n "$DEBUG" ]
        then
            echo curl -L -X PUT -H 'Content-Type:application/octet-stream' -H "X-Gitlab-Token:xxxxxxxxxxx" -T "$file" "$server_url/$(urlencode "${file##*/}")"
        fi
        curl -L -X PUT -H 'Content-Type:application/octet-stream' -H "X-Gitlab-Token:$GITLAB_TOKEN" -T "$file" "$server_url/$(urlencode "${file##*/}")"
        echo "File '$file' uploaded to '$server_url/$(urlencode "${file##*/}")'"
    fi

    # Check if the current item is a directory
    if [ -d "$file" ]
    then
        # Recursively call the script on the subdirectory
        if [ -n "$DEBUG" ]
        then
            echo "$0" "$file" "$project_id" "$sub_path/$(urlencode "${file##*/}")"
        fi
        "$0" "$file" "$project_id" "$sub_path/$(urlencode "${file##*/}")"
    fi
done

echo "Upload done..."
echo "You can access your files using the following command:"
echo "curl -L -H 'X-Gitlab-Token:YOUR_GITLAB_TOKEN' <the_file_url_as_above>"
```
