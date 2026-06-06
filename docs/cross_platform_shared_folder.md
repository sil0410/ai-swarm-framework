# Cross-platform shared folder / NAS setup

AI Swarm Framework only needs a shared folder that all machines can access.

It can be:

- NAS share
- Samba share
- SMB share
- NFS mount
- Syncthing folder
- OneDrive/Dropbox/iCloud folder, if file conflicts are acceptable

## Windows

Examples:

```text
//server/share/AI_ControlCenter
\\server\share\AI_ControlCenter
Z:/AI_ControlCenter
```

## macOS

Mount SMB in Finder or command line, then use a path like:

```text
/Volumes/AI_ControlCenter
```

## Linux

Mount SMB/NFS to a local path, for example:

```text
/mnt/AI_ControlCenter
```

## Important

The path does not need to be identical across machines.

Each node stores its own `.node_config.json` with:

- its agent identity
- its shared folder path
- its local working copy path
- its OS

## Sync safety

The included sync helper copies files from shared folder to local working copy.

It does not propagate deletes.

Avoid any command that deletes shared data automatically unless you fully understand the consequences.
