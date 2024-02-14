# :simple-gitlfs: Git LFS

Git LFS (Large File Storage) is an extension for Git, a widely used version control system, designed to handle large files more efficiently. As the name suggests, Git LFS is primarily used for storing large binary files, such as images, audio/video files, datasets, and other non-textual data, which traditional Git struggles to manage effectively due to its inherent limitations.

If your GitLab instance supports Git LFS, SharingHub can work with it, and files stored with LFS in the STAC Item's assets are downloadable just like any other file.

- [🔗 Official website](https://git-lfs.com/)

!!! note

    While Git LFS can handle _larger_ files than Git, the size limit per repository is by default of 5GB. For really big data volumes, another supported solution can be used, [DVC](./dvc.md).
