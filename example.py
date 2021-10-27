"""Bamboo customisation for CMS RTB flat trees, and an example analysis module"""

#############################################################################
## Base modules, to be moved to a separate package, or bundled with bamboo ##
#############################################################################

from bamboo.analysismodules import AnalysisModule, HistogramsModule
import logging
logger = logging.getLogger(__name__)

class CMSPhase2SimRTBModule(AnalysisModule):
    """ Base module for processing Phase2 flat trees """
    def __init__(self, args):
        super(CMSPhase2SimRTBModule, self).__init__(args)
        self._h_genwcount = {}
    def prepareTree(self, tree, sample=None, sampleCfg=None):
        from bamboo.treedecorators import decorateCMSPhase2SimTree
        from bamboo.dataframebackend import DataframeBackend
        t = decorateCMSPhase2SimTree(tree, isMC=True)
        be, noSel = DataframeBackend.create(t)
        from bamboo.root import gbl
        self._h_genwcount[sample] = be.rootDF.Histo1D(
                gbl.ROOT.RDF.TH1DModel("h_count_genweight", "genweight sum", 1, 0., 1.),
                "_zero_for_stats",
                "genweight"
                )
        return t, noSel, be, tuple()
    def mergeCounters(self, outF, infileNames, sample=None):
        outF.cd()
        self._h_genwcount[sample].Write("h_count_genweight")
    def readCounters(self, resultsFile):
        return {"sumgenweight": resultsFile.Get("h_count_genweight").GetBinContent(1)}

class CMSPhase2SimRTBHistoModule(CMSPhase2SimRTBModule, HistogramsModule):
    """ Base module for producing plots from Phase2 flat trees """
    def __init__(self, args):
        super(CMSPhase2SimRTBHistoModule, self).__init__(args)

################################
## An analysis module example ##
################################

class SnowmassExample(CMSPhase2SimRTBHistoModule):
    def addArgs(self, parser):
        super().addArgs(parser)
        parser.add_argument("--mvaSkim", action="store_true", help="Produce MVA training skims")
        parser.add_argument("--datacards", action="store_true", help="Produce histograms for datacards")

    def definePlots(self, t, noSel, sample=None, sampleCfg=None):
        from bamboo.plots import Plot, CutFlowReport
        from bamboo.plots import EquidistantBinning as EqB
        from bamboo import treefunctions as op

        noSel = noSel.refine("withgenweight", weight=t.genweight)

        plots = []

        electrons = op.select(t.elec, lambda el : op.AND(
            el.pt > 20.,
            op.abs(el.eta) < 2.5
            ))

        hasTwoEl = noSel.refine("hasElEl", cut=(op.rng_len(electrons) >= 2))

        plots.append(Plot.make1D("2El_nJets", op.rng_len(t.jetpuppi), hasTwoEl, EqB(10, 0., 10.), title="nJets"))

        if self.args.mvaSkim:
            from bamboo.plots import Skim
            plots.append(Skim("allevts", {
                "weight": noSel.weight,
                "nElectrons": op.rng_len(electrons),
                #"El_pt": op.map(electrons, lambda el : el.pt)
                }, noSel))

        yields = CutFlowReport("yields")
        plots.append(yields)
        yields.add(noSel, "Produced")
        yields.add(hasTwoEl, "2 electrons")

        return plots

    def postProcess(self, taskList, config=None, workdir=None, resultsdir=None):
        super().postProcess(taskList, config=config, workdir=workdir, resultsdir=resultsdir)
        import os.path
        from bamboo.plots import Skim
        skims = [ap for ap in self.plotList if isinstance(ap, Skim)]
        from bamboo.analysisutils import loadPlotIt
        if self.args.mvaSkim and skims:
            p_config, samples, _, systematics, legend = loadPlotIt(
                config, [], eras=self.args.eras[1], workdir=workdir, resultsdir=resultsdir,
                readCounters=self.readCounters, vetoFileAttributes=self.__class__.CustomSampleAttributes)
            try:
                from bamboo.root import gbl
                import pandas as pd
                for skim in skims:
                    frames = []
                    for smp in samples:
                        for cb in (smp.files if hasattr(smp, "files") else [smp]):  # could be a helper in plotit
                            cols = gbl.ROOT.RDataFrame(cb.tFile.Get(skim.treeName)).AsNumpy()
                            cols["weight"] *= cb.scale
                            cols["process"] = [smp.name]*len(cols["weight"])
                            frames.append(pd.DataFrame(cols))
                    df = pd.concat(frames)
                    df["process"] = pd.Categorical(df["process"], categories=pd.unique(df["process"]), ordered=False)
                    pqoutname = os.path.join(resultsdir, f"{skim.name}.parquet")
                    df.to_parquet(pqoutname)
                    logger.info(f"Dataframe for skim {skim.name} saved to {pqoutname}")
            except ImportError as ex:
                logger.error("Could not import pandas, no dataframes will be saved")
        if self.args.datacards:
            # the code below will produce histograms "with datacard conventions":
            # - scaled with lumi and cross-section
            # - "region.root:/h_process"
            # in practice shape systematics and renamings/regroupings may be needed,
            # see https://gitlab.cern.ch/piedavid/cms-ttw-run2legacy/-/blob/bamboo/ttW/datacards.py
            # for an example with a number of such things implemented
            datacardPlots = [ap for ap in self.plotList if ap.name =="2El_nJets"]
            p_config, samples, plots_dc, systematics, legend = loadPlotIt(
                config, datacardPlots, eras=self.args.eras[1], workdir=workdir, resultsdir=resultsdir,
                readCounters=self.readCounters, vetoFileAttributes=self.__class__.CustomSampleAttributes)
            dcdir = os.path.join(workdir, "datacard_histograms")
            import os
            os.makedirs(dcdir, exist_ok=True)
            def _saveHist(obj, name, tdir=None):
                if tdir:
                    tdir.cd()
                obj.Write(name)
            from functools import partial
            import plotit.systematics
            from bamboo.root import gbl
            for plot in plots_dc:
                for era in (self.args.eras[1] or config["eras"].keys()):
                    f_dch = gbl.TFile.Open(os.path.join(dcdir, f"{plot.name}_{era}.root"), "RECREATE")
                    saveHist = partial(_saveHist, tdir=f_dch)
                    for smp in samples:
                        smpName = smp.name
                        if smpName.endswith(".root"):
                            smpName = smpName[:-5]
                        h = smp.getHist(plot, eras=era)
                        saveHist(h.obj, f"h_{smpName}")
                    f_dch.Close()
