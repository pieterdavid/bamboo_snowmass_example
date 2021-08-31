# Analyze Delphes-ntuplized files with bamboo

This repository contains example code to analyse
[Delphes-Ntuplized](https://github.com/recotoolsbenchmarks/DelphesNtuplizer) samples
(from the CMS Snowmass production) with [bamboo](https://gitlab.cern.ch/cp3-cms/bamboo).

To install [bamboo](https://gitlab.cern.ch/cp3-cms/bamboo) follow [these instructions](https://bamboo-hep.readthedocs.io/en/latest/install.html).

The example module defined [here](example.py#L41-L58) can be run with
```bash
bambooRun -m example.py:SnowmassExample example.yml -o test1
```

Feel free to report problems any problems with this example,
accessing the information in the files, or the framework in general
as an issue here, in the [~bamboo](https://mattermost.web.cern.ch/cms-exp/channels/bamboo)
channel on the CERN mattermost instance, or on
[Gitlab](https://gitlab.cern.ch/cp3-cms/bamboo/-/issues).
