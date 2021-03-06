"""
Study the MET distibutions and various PUS schemes
"""
from __future__ import division
import numpy as np
import ROOT
import os
from cmsl1t.analyzers.BaseAnalyzer import BaseAnalyzer
from cmsl1t.plotting.rates import RatesPlot
from cmsl1t.plotting.rate_vs_pileup import RateVsPileupPlot
from cmsl1t.filters import LuminosityFilter
import cmsl1t.hist.binning as bn
from cmsl1t.utils.hist import cumulative_hist, normalise_to_collision_rate


def types():
    sum_types = ["HT", "METBE", "METHF"]
    jet_types = ["JetET_BE", "JetET_HF"]
    sum_types += [t + '_Emu' for t in sum_types]
    jet_types += [t + '_Emu' for t in jet_types]

    return sum_types, jet_types


def extractSums(event):
    online = dict(
        HT=event.l1Sums_Htt,
        METBE=event.l1Sums_Met,
        METHF=event.l1Sums_MetHF,
        HT_Emu=event.l1EmuSums_Htt,
        METBE_Emu=event.l1EmuSums_Met,
        METHF_Emu=event.l1EmuSums_MetHF,
    )

    return online


# Eta ranges so we can put |\eta| < val as the legend header on the
# efficiency plots.
ETA_RANGES = dict(
    HT="|\\eta| < 2.4",
    METBE="|\\eta| < 3.0",
    METHF="|\\eta| < 5.0",
    JetET_BE="|\\eta| < 3.0",
    JetET_HF="3.0 < |\\eta| < 5.0",
    HT_Emu="|\\eta| < 2.4",
    METBE_Emu="|\\eta| < 3.0",
    METHF_Emu="|\\eta| < 5.0",
    JetET_BE_Emu="|\\eta| < 3.0",
    JetET_HF_Emu="3.0 < |\\eta| < 5.0",
)


class Analyzer(BaseAnalyzer):

    def __init__(self, **kwargs):
        super(Analyzer, self).__init__(**kwargs)
        self.triggerName = self.params['triggerName']
        self.thresholds = self.params['thresholds']
        self.puBins = self.params['pu_bins']

        self._lumiFilter = None
        self._lumiJson = self.params['lumiJson']
        if self._lumiJson:
            self._lumiFilter = LuminosityFilter(self._lumiJson)

        self._lastRunAndLumi = (-1, -1)
        self._processLumi = True
        self._sumTypes, self._jetTypes = types()

        for name in self._sumTypes + self._jetTypes:
            rates_plot = RatesPlot(name)
            self.register_plotter(rates_plot)
            setattr(self, name + "_rates", rates_plot)

            rate_vs_pileup_plot = RateVsPileupPlot(name)
            self.register_plotter(rate_vs_pileup_plot)
            setattr(self, name + "_rate_vs_pileup", rate_vs_pileup_plot)

    def prepare_for_events(self, reader):
        # bins = np.arange(0.0, 400.0, 1.0)
        puBins = self.puBins
        thresholds = self.thresholds

        for name in self._sumTypes + self._jetTypes:
            trig_thresholds = thresholds.get(name)
            if(trig_thresholds is None):
                if "Emu" in name:
                    trig_thresholds = thresholds.get(name.replace('_Emu', ''))
                else:
                    print(
                        'Error: Please specify thresholds in the config .yaml in dictionary format')

            rates_plot = getattr(self, name + "_rates")
            rates_plot.build(name, puBins, 200, 0, 200, ETA_RANGES.get(name))

            rate_vs_pileup_plot = getattr(self, name + "_rate_vs_pileup")
            rate_vs_pileup_plot.build(
                "L1 " + name, trig_thresholds, 16, 0, 80, ETA_RANGES.get(name))

        '''
        self.rates = HistogramsByPileUpCollection(
            pileupBins=puBins, dimensions=2)
        for thing in object_types:
            self.rates.add(thing, bins)
        '''

        return True

    '''
    def reload_histograms(self, input_file):
        # Something like this needs to be implemented still
        self.rates = HistogramsByPileUpCollection.from_root(input_file)
        return True
    '''

    def fill_histograms(self, entry, event):
        if not self._passesLumiFilter(event['run'], event['lumi']):
            return True
        # Get pileup if ntuples have reco trees in them.
        # If not, set PU to 1 so that it fills the (only) pu bin.

        try:
            pileup = event.nVertex
        except AttributeError:
            pileup = 1.

        # Sums:
        online = extractSums(event)
        for name in self._sumTypes:
            on = online[name]
            getattr(self, name + "_rates").fill(pileup, on.et)
            getattr(self, name + "_rate_vs_pileup").fill(pileup, on.et)

        # All jets:
        l1JetEts = [jet.et for jet in event.l1Jets]
        nJets = len(l1JetEts)
        if nJets > 0:
            maxL1JetEt = max(l1JetEts)
        else:
            maxL1JetEt = 0.

        l1EmuJetEts = [jet.et for jet in event.l1EmuJets]
        nEmuJets = len(l1EmuJetEts)
        if nEmuJets > 0:
            maxL1EmuJetEt = max(l1EmuJetEts)
        else:
            maxL1EmuJetEt = 0.

        # Central Jets:
        l1BEJets = [jet for jet in event.l1Jets if abs(jet.eta) < 3.0]
        l1BEJetEts = [beJet.et for beJet in l1BEJets]
        nBEJets = len(l1BEJets)
        if nBEJets > 0:
            maxL1BEJetEt = max(l1BEJetEts)
        else:
            maxL1BEJetEt = 0.

        l1EmuBEJets = [jet for jet in event.l1EmuJets if abs(jet.eta) < 3.0]
        l1EmuBEJetEts = [beJet.et for beJet in l1EmuBEJets]
        nEmuBEJets = len(l1EmuBEJetEts)
        if nEmuBEJets > 0:
            maxL1EmuBEJetEt = max(l1EmuBEJetEts)
        else:
            maxL1EmuBEJetEt = 0.

        # Forward Jets
        l1HFJets = [jet for jet in event.l1Jets if abs(jet.eta) > 3.0]
        l1HFJetEts = [hfJet.et for hfJet in l1HFJets]
        nHFJets = len(l1HFJetEts)
        if nHFJets > 0:
            maxL1HFJetEt = max(l1HFJetEts)
        else:
            maxL1HFJetEt = 0.

        l1EmuHFJets = [jet for jet in event.l1EmuJets if abs(jet.eta) > 3.0]
        l1EmuHFJetEts = [hfJet.et for hfJet in l1EmuHFJets]
        nEmuHFJets = len(l1EmuHFJetEts)
        if nEmuHFJets > 0:
            maxL1EmuHFJetEt = max(l1EmuHFJetEts)
        else:
            maxL1EmuHFJetEt = 0.

        for name in self._jetTypes:
            if 'Emu' in name:
                if 'BE' in name:
                    getattr(self, name + '_rates').fill(pileup, maxL1EmuBEJetEt)
                    getattr(self, name + '_rate_vs_pileup').fill(pileup,
                                                                 maxL1EmuBEJetEt)
                elif 'HF' in name:
                    getattr(self, name + '_rates').fill(pileup, maxL1EmuHFJetEt)
                    getattr(self, name + '_rate_vs_pileup').fill(pileup,
                                                                 maxL1EmuHFJetEt)
                else:
                    getattr(self, name + '_rates').fill(pileup, maxL1EmuJetEt)
                    getattr(self, name +
                            '_rate_vs_pileup').fill(pileup, maxL1EmuJetEt)
            else:
                if 'BE' in name:
                    getattr(self, name + '_rates').fill(pileup, maxL1BEJetEt)
                    getattr(self, name +
                            '_rate_vs_pileup').fill(pileup, maxL1BEJetEt)
                elif 'HF' in name:
                    getattr(self, name + '_rates').fill(pileup, maxL1HFJetEt)
                    getattr(self, name +
                            '_rate_vs_pileup').fill(pileup, maxL1HFJetEt)
                else:
                    getattr(self, name + '_rates').fill(pileup, maxL1JetEt)
                    getattr(self, name +
                            '_rate_vs_pileup').fill(pileup, maxL1JetEt)

        return True

    def _passesLumiFilter(self, run, lumi):
        if self._lumiFilter is None:
            return True
        if (run, lumi) == self._lastRunAndLumi:
            return self._processLumi

        self._lastRunAndLumi = (run, lumi)
        self._processLumi = self._lumiFilter(run, lumi)

        return self._processLumi

    def make_plots(self):
        # TODO: implement this in BaseAnalyzer
        # make_plots -> make_plots(plot_func)

        # Get EMU thresholds for each HW threshold.

        if 'thresholds' not in self.params:
            print(
                'Error: Please specify thresholds in the config .yaml in dictionary format')

        # print hw vs emu for rates and rate vs pileup
        for histo_name in self._sumTypes + self._jetTypes:
            if "_Emu" in histo_name:
                continue
            plotter = getattr(self, histo_name + '_rates')
            emu_plotter = getattr(self, histo_name + '_Emu_rates')
            plotter.overlay_with_emu(emu_plotter)

            plotter = getattr(self, histo_name + '_rate_vs_pileup')
            emu_plotter = getattr(self, histo_name + "_Emu" + '_rate_vs_pileup')
            plotter.overlay_with_emu(emu_plotter)

        # calculate cumulative histograms
        for plot in self.all_plots:
            if 'rate_vs_pileup' not in plot.filename_format:
                hist = plot.plots.get_bin_contents([bn.Base.everything])
                hist = cumulative_hist(hist)
                hist = normalise_to_collision_rate(hist)
                setattr(self, plot.online_name, hist)
                # plot.draw()

        print('  thresholds:')

        for histo_name in self._sumTypes + self._jetTypes:
            if "_Emu" in histo_name:
                continue
            h = getattr(self, histo_name)
            h_emu = getattr(self, histo_name + "_Emu")
            bin1 = h.get_bin_content(1)
            if bin1 != 0.:
                h.Scale(40000000. / bin1)
            bin1_emu = h_emu.get_bin_content(1)
            if bin1_emu != 0.:
                h_emu.Scale(40000000. / bin1_emu)
            thresholds = self.thresholds.get(histo_name)
            emu_thresholds = []
            for thresh in thresholds:
                rate_delta = []
                hw_rate = h.get_bin_content(thresh)
                for i in range(h.nbins()):
                    emu_rate = h_emu.get_bin_content(i)
                    if hw_rate == 0. or emu_rate == 0.:
                        rate_delta.append(40000000.)
                    else:
                        rate_delta.append(abs(hw_rate - emu_rate))
                emu_thresholds.append(rate_delta.index(min(rate_delta)))
            outputline = ('    {0}: {1}'.format(histo_name, thresholds) +
                          '\n' + '    {0}: {1}'.format(histo_name + '_Emu', emu_thresholds))
            print(outputline)

        '''
        for histo_name in object_types:
            h = getattr(self, histo_name)
            plot(h, histo_name, self.output_folder)
        '''
        return True


def plot(hist, name, output_folder):
    pu = ''
    if '_pu' in name:
        pu = name.split('_')[-1]
        name = name.replace('_' + pu, '')
    file_name = 'rates_{name}'.format(name=name)
    if 'nVertex' in name:
        file_name = 'nVertex'
    if pu:
        file_name += '_' + pu
    canvas_name = file_name.replace('SingleMu', 'Rates')
    c = ROOT.TCanvas(canvas_name)
    if 'nVertex' not in name:
        c.SetLogy()
    hist.set_y_title('Rate (Hz)')
    hist.set_x_title(name)
    hist.Draw()
    c.SaveAs(os.path.join(output_folder, file_name + '.pdf'))
