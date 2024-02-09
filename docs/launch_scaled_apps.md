## Launching applications in scaled mode

When launching an application with the `nuvolos apps start` command, you can use the `-n` option to specify the nodepool for your application, where your application will run on a dedicated node. With this flag you can run your application with higher computing capacity and/or a GPU.

!!! warning

    Running your application on a dedicated node is charged against credits of the underlying account. For further information, 
    see the related section in the [Nuvolos documentation](https://docs.nuvolos.cloud/user-guides/research-guides/high-performance-computing#how-to-scale-your-app).

If the application to run is configured to launch in scaled mode by default, but you would like to start it in 
a normal, NCU-based mode, you can explicitly pass the `-n ""` option to override the default node pool settings. Your app will start with the configured NCUs in this case.

## Selecting the scaled node
You can list all available nodepools with the following command:
```
nuvolos apps nodepools
```
The `memory`, `ssd` and `vram` attributes are expressed in `GB`, while the `cpu` is expressed as the number of vCPUs.


In order to start your application on a **dedicated high-performance compute node**, you should pass the
chosen node's `slug` to the `-n` option when starting the application.