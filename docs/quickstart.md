# Quickstart

You can launch the Nuvolos CLI with the `nuvolos` command.

If you are running the CLI on your own computer, you will need to configure your API key. You can do this with the `nuvolos config` command:

```
nuvolos config --api-key <YOUR_API_KEY>
```

**On the Nuvolos platform, you can use the CLI without any configuration.**

To list the applications available in the current instance you are working in, you can use the `nuvolos apps list` command:

```
nuvolos apps list
```

To launch an application, you can use the `nuvolos apps start` command:

```
nuvolos apps start -a <aid>
```
where `<aid>` is the application ID. You can find the application ID in the output of the `nuvolos apps list` command.

You can list all running apps with the `nuvolos apps command`:

```
nuvolos apps running
```

You can stop an application with the `nuvolos apps stop` command:

```
nuvolos apps stop -a <aid>
```

