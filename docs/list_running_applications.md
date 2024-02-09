# List running applications

To list all your running applications on Nuvolos, run
```
nuvolos apps running
```
Before executing commands, it's advisable to verify the state of an application. You can list
the running applications with a given slug within a designated context by running
```
nuvolos apps running -o <org_slug> -s <space_slug> -i <instance_slug> -a <app_slug> 
```
On Nuvolos, you can omit the `-o`, `-s`, `-i` options if your target application is running in the same instance.

When the application is not running, the command will return an empty list. If the app is active, you can monitor
its state by inspecting the `status` field in the response. Possible states are `RUNNING`, `STARTING` and `STOPPING`.

!!! note 

    When specifying the `app_slug`, the command yields a list of running applications associated with the provided identifier. 
    This includes applications initiated by the current user, as well as applications running in shared mode and accessible to the current user.