# Project view

The main SharingHub view, shown below, is designed to display as much metadata as possible about a project, whether it's an AI model, a dataset, a tool/library or a challenge.

![category overview](figures/project-view/category_overview.png)

## 1. Project title Section

This section is made up of the project's name as described in GitLab and a link that takes you directly to the repository where the project is hosted.

## 2. Keywords/Tags Section

This section displays all the keywords and licenses related to the project in GitLab. It's important because it's used as a label to filter out projects with common criteria or specifications. Moreover, tags are used to improve searches, as described in the [tag search section](./search.md#tag-search-tab).

## 3. Controls Button set

This important section allows you to interact with the project with the following functionalities:

### Open project in Jupyter Notebook

If the SharingHub is configured with a notebook service, this button will appear, allowing you to open the project, in particular your AI model in a notebook, for testing or manipulation in a dedicated environment.

![open in notebook](figures/project-view/category_overview_notebook.png)

When you click the open button, the Jupyter environment is launched to open the target Notebook.
Click on the "Launch Server" button.
At next page, select "vreot-cloud" environment and click on "Start" button.

![start vre](figures/project-view/category_overview_start_jupyter1.png)

![start vre](figures/project-view/category_overview_start_jupyter2.png)

![vre launched with project](figures/project-view/category_overview_vre_launched.png)

!!! info
    **_Configure destination folder_**

    The project is cloned by default in your Jupyter environment home folder.
    If you prefer to customize that behaviour, it is required to set an environment variable into Jupyter.
    To do so, you have to initialize a user Jupyter configuration file.
    Into Jupyter, open a terminal and execute:

    ```bash
    jupyter notebook --generate-config
    vim ~/.jupyter/jupyter_notebook_config.py
    ```

    and add into that file:

    ```python
    import os
    os.environ["NBGITPULLER_PARENTPATH"] = "destination_folder"
    ```

    with "destination_folder" the relative path from your home folder where you want projects to be cloned.

    Finally, restart Jupyter for that configuration to be applied.

### Display DVC information

The DVC service enables you to store large volumes of data. The DVC button is therefore only displayed for projects in the "Datasets" category, which have a DVC configuration in the source GitLab project.  This button displays the remote DVC configuration link and additional information on the DVC [documentation](https://dvc.org/doc) and [tutorial](../tutorials/manage_dataset_with_dvc.md).

![dvc button](figures/project-view/category_overview_dvc.png)

### Share the project

The share button lets you share a direct link to the project with other colleagues.

![share project](figures/project-view/category_overview_share.png)

### Star the project

If you like the project, you will be able to star it and it will appear in your [favorite projects](./search.md#filter-by-starred-projects).

![star project](figures/project-view/category_overview_star.png)
![unstar project](figures/project-view/category_overview_unstar.png)

!!! Note Warning

    If the default token is enabled, filter by star button is not visible because we are in read-only mode.

    ![control set limitless](figures/project-view/category_overview_limitless.png)

## 4. Dynamics Tabs

This section displays details, comments and the STAC API in tabbed format.

### Details Tab

This "details" tab displays the project description first. This view highlights all the project's files and resources in the "assets" section, and thanks to the "additional resources" section it's possible to see references to other projects or resources.

![detail tab](figures/project-view/dynamic_tab-detail.png)

In some cases, and more generally for datasets, the details tab may show a map with an area corresponding to the geographic extent of the dataset.

![detail tab show map](figures/project-view/dynamic_tab-map.png)

### Reviews Tab

This section is a discussion forum for the project, allowing contributors to leave notes and ask questions to each other.

![review tab](figures/project-view/dynamics_tab-review.png)

### STAC API Tab

This section shows the STAC API informations of the project, the link to the STAC file of the project and also checks if the project is valid according to the supported STAC extensions.

![STAC Api tab ](figures/project-view/dynamic_tab-api.png)
