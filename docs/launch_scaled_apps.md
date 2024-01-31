## Launching applications in scaled mode

When launching an application with the `nuvolos apps start` command, you can use the `-n` argument to specify the node
pool where the application should run. With this flag you can run your application in scaled mode with higher computing
capacity and/or a GPU. 

!!! Note
Running your application in scaled mode is charged against credits of the unerlying account. For further information, 
see the related section in the [Nuvolos documentation](https://docs.nuvolos.cloud/user-guides/research-guides/high-performance-computing#how-to-scale-your-app).

## Selecting the scaled node
You can list all available nodes with the following command:
```
nuvolos apps nodes
```
The `memory`, `ssd` and `vram` attributes are expressed in `GB`, while the `cpu` is expressed as the number of vCPUs.


In order to start your application in a scaled mode on a **dedicated high-performance compute node**, you should pass the
chosen node's `slug` to the `-n` argument when starting the application.