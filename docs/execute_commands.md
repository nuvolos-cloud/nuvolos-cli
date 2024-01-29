# Execute commands

With the nuvolos API you can execute commands in your running Nuvolos applications with the `nuvolos apps execute` command:
```
nuvolos apps execute -o <org_slug> -s <space_slug> -i <instance_slug> -a <app_slug> -c <command>
```

## Selecting the application for Command Execution
Commands can only be run in a Nuvolos application that is in a RUNNING state. To verify the running status of your app, you can refer to the **TODO add reference**.

On Nuvolos, you can omit the `-o`, `-s`, `-i` flags if your target application is running in the same instance.
However, if you'd like to submit a command to an application that is running in a separate instance, you need to specify the context for that application with the `-o`, `-s`, `-i` flags.

## Submitting a command for execution
You can submit multiple commands to a running Nuvolos application by making multiple calls the `nuvolos apps execute` command. 
The command execution mirrors the behavior of the terminal in your Nuvolos application when accessed through the UI.
For example, you can run `.py` files in a JupyterLab application by calling 
```
nuvolos apps execute -a your_app_slug -c 'python your_file.py'
```

The default working directory for command execution is the same as the interactive terminals in the selected applications, the `/files` folder.

## Storing metadata about the submitted commands
Upon every command execution a new folder is created under the `/files/nuvolos_api_out` folder in a `<timestamp>_<request_id>` format,
where the request id (`reqid`) is returned by the cli command. A `metadata.json` file is created to store details 
such as the application context, submission timestamp, and the submitted command.

## Accessing standard output and standard error
By default, the standard output and the standard error of your command are redirected to separate files to ensure preservation.
The files are located in the folder introduced above, called `output.log` and `error.log`, respectively.

You can overwrite this redirection by defining your own in the submitted command, e.g:
```
nuvolos apps execute -a your_app_slug -c 'python your_file.py> myoutput.log, 2> myerror.log'
```
that will save the `stdout` and `stderr` of your command to the defined files in the working directory.

!!! note
`nuvolos apps execute` supports output redirect when exactly one command is submitted. If you submitted a command sequence
(e.g. `python prepare.py && python evaluate.py`), you need to specify the files where you intend to redirect the `stdout` and `stderr`
of each command, otherwise only the results of the last command will be saved in the default location.

## Managing Workflow Dependencies
In the scenario where you've established a workflow with one application depending on the outcomes of another, the `/files` folder 
serves as a convenient storage space for files accessible to both applications, provided they reside within the same instance. 
If you wish to share results between applications located in separate instances, consider utilizing the [Large File Storage](https://docs.nuvolos.cloud/features/file-system-and-storage/large-file-storage)
feature on Nuvolos.