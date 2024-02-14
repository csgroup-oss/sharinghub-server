# :simple-dvc: DVC

DVC (Data Version Control) is an open-source version control system specifically designed for machine learning (ML) and data science projects. It complements traditional version control systems like Git by focusing on managing the large datasets and machine learning models typically used in these domains. DVC provides a simple yet powerful set of tools to track changes, collaborate, and reproduce experiments with data and ML models efficiently. DVC allows you to version control datasets alongside your code. It stores lightweight metafiles in Git to track changes to datasets, while the actual data files are stored separately, typically in cloud storage or network-attached storage (NAS).

Your deployment of SharingHub may support DVC, and offer a DVC remote with an S3 storage behind. If a project uses DVC, you can see the [DVC button](../../explore/project-view.md#display-dvc-information) being displayed. To learn more about the usage of DVC, and our store remote, checkout the dedicated [tutorial](../../tutorials/manage_dataset_with_dvc.md).

- [🔗 Official website](https://dvc.org/)
- [🔗 Documentation](https://dvc.org/doc)
