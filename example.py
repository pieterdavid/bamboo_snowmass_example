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
        if self.args.mvaSkim and skims:
            # Calculate the scale for each sample
            lumiPerEra = {era: eraCfg["luminosity"] for era, eraCfg in config["eras"].items()}
            filesAndNorms = {}
            from bamboo.root import gbl
            for smpNm, smpCfg in config["samples"].items():
                resF = gbl.TFile.Open(os.path.join(resultsdir, f"{smpNm}.root"))
                genEvts = None
                if "generated-events" in smpCfg:
                    if isinstance(smpCfg["generated-events"], str):
                        genEvts = self.readCounters(resF)[smpCfg["generated-events"]]
                    else:
                        genEvts = smpCfg["generated-events"]
                norm = (lumiPerEra[smpCfg["era"]]
                       * smpCfg.get("cross-section", 1.)
                       * smpCfg.get("branching-ration", 1.)
                       / genEvts)
                filesAndNorms[smpNm] = (resF, norm)
            try:
                import pandas as pd
                for skim in skims:
                    # Read and scale results for all samples, and save the dataframe
                    frames = []
                    for smpNm,(resF, norm) in filesAndNorms.items():
                        cols = gbl.ROOT.RDataFrame(resF.Get(skim.treeName)).AsNumpy()
                        cols["weight"] *= norm
                        proc = config["samples"][smpNm].get("group", smpNm)
                        cols["process"] = [proc]*len(cols["weight"])
                        frames.append(pd.DataFrame(cols))
                    df = pd.concat(frames)
                    categoriess = set(df["process"])
                    df["process"] = pd.Categorical(df["process"], categories=list(categoriess), ordered=False)
                    pqoutname = os.path.join(resultsdir, f"{skim.name}.parquet")
                    df.to_parquet(pqoutname)
                    logger.info(f"Dataframe for skim {skim.name} saved to {pqoutname}")
            except ImportError as ex:
                logger.error("Could not import pandas, no dataframes will be saved")
