"""Bamboo customisation for CMS RTB flat trees, and an example analysis module"""

#############################################################################
## Base modules, to be moved to a separate package, or bundled with bamboo ##
#############################################################################

from bamboo.analysismodules import AnalysisModule, HistogramsModule

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

        if False:
            # this needs "pip install --upgrade 'git+https://gitlab.cern.ch/cp3-cms/bamboo.git@refs/merge-requests/196/head#egg=bamboo' "
            # until https://gitlab.cern.ch/cp3-cms/bamboo/-/merge_requests/196 is merged (so disabled by default)
            from bamboo.plots import Skim
            plots.append(Skim("allevts", {
                "weight": noSel.weight,
                "nElectrons": op.rng_len(electrons),
                "El_pt": op.map(electrons, lambda el : el.pt)
                }, noSel))

        yields = CutFlowReport("yields")
        plots.append(yields)
        yields.add(noSel, "Produced")
        yields.add(hasTwoEl, "2 electrons")

        return plots
