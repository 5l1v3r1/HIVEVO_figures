import numpy as np
from itertools import izip
from hivevo.hivevo.patients import Patient
from hivevo.hivevo.HIVreference import HIVreference
from hivevo.hivevo.af_tools import divergence
from util import store_data, load_data, fig_width, fig_fontsize, add_binned_column
import os
from filenames import get_figure_folder

def get_quantiles(q, arr):
    from scipy.stats import scoreatpercentile
    thresholds = [scoreatpercentile(arr, 100.0*i/q) for i in range(q+1)]
    return {i: {'range':(thresholds[i],thresholds[i+1]), 
                'ind':((arr>=thresholds[i])*(arr<thresholds[i+1]))}
           for i in range(q)}



def plot_to_away(data, fig_filename = None, figtypes=['.png', '.svg', '.pdf']):
    ####### plotting ###########
    import seaborn as sns
    from matplotlib import pyplot as plt
    plt.ion()
    sns.set_style('darkgrid')
    figpath = 'figures/'
    fs=fig_fontsize
    fig_size = (fig_width, 0.8*fig_width)
    fig, axs = plt.subplots(1, 1, figsize=fig_size)

    ax=axs
    Sbins = np.array([0,0.02, 0.08, 0.25, 2])
    Sbinc = 0.5*(Sbins[1:]+Sbins[:-1])
    mv = data['minor_variants']
    add_binned_column(mv, Sbins, 'S')
    mean_to_away = mv.groupby(by=['S_bin','away'], as_index=False).mean()
    print mean_to_away

    ax.plot(Sbinc, mean_to_away.loc[mean_to_away.loc[:,'away']==True,'af_minor']   , label = 'equal subtype')
    ax.plot(Sbinc, mean_to_away.loc[mean_to_away.loc[:,'away']==False,'af_minor']  , label = 'not equal subtype')
    #ax.plot(Sbinc, mean_to_away.loc[mean_to_away.loc[:,'away']==True,'af_derived'] , label = 'away, der')
    #ax.plot(Sbinc, mean_to_away.loc[mean_to_away.loc[:,'away']==False,'af_derived'], label = 'to, der')
    ax.set_yscale('log')
    ax.set_xscale('log')
    ax.set_ylabel('minor SNV frequencies')
    ax.set_xlabel('entropy [bits]')
    ax.set_xlim([0.005,2])
    ax.legend(loc = 'bottom right')

    to_away = data['to_away']
    time_bins = np.array([0,200,500,1000,1500, 2500, 3500])
    binc = 0.5*(time_bins[1:]+time_bins[:-1])
    add_binned_column(to_away, time_bins, 'time')
    reversion = to_away.loc[:,['reversion','time_bin']].groupby(by=['time_bin'], as_index=False).mean()
    total_div = to_away.loc[:,['divergence','time_bin']].groupby(by=['time_bin'], as_index=False).mean()
    print "Reversions:\n", reversion
    print "Divergence:\n", total_div
    print "Fraction:\n", reversion.loc[:,'reversion']/total_div.loc[:,'divergence']
    print "Consensus!=Founder:",np.mean(data['consensus_distance'])

    plt.tight_layout(rect=(0.0, 0.02, 0.98, 0.98), pad=0.05, h_pad=0.5, w_pad=0.4)
    if fig_filename is not None:
        for ext in figtypes:
            fig.savefig(fig_filename+'_sfs'+ext)
    else:
        plt.ion()
        plt.show()


if __name__=="__main__":
    import argparse
    import matplotlib.pyplot as plt
    import pandas as pd
    parser = argparse.ArgumentParser(description="make figure")
    parser.add_argument('--redo', action = 'store_true', help = 'recalculate data')
    params=parser.parse_args()

    username = os.path.split(os.getenv('HOME'))[-1]
    foldername = get_figure_folder(username, 'first')
    fn_data = foldername+'data/'
    fn_data = fn_data + 'to_away.pickle'
    
    if not os.path.isfile(fn_data) or params.redo:
        patients = ['p2', 'p3','p5', 'p8', 'p9', 'p10','p11']
        regions = ['genomewide']
        #regions = ['gag', 'pol', 'env']
        #regions = ['p24', 'p17'] #, 'RT1', 'RT2', 'RT3', 'RT4', 'PR', 
        #           'IN1', 'IN2', 'IN3','p15', 'vif', 'nef','gp41','gp1201']
        cov_min = 1000
        hxb2 = HIVreference(refname='HXB2')
        good_pos_in_reference = hxb2.get_ungapped(threshold = 0.05)
        minor_variants = []
        consensus_distance = []
        # determine genome wide fraction of alleles above a threshold
        for pi, pcode in enumerate(patients):
            try:
                p = Patient.load(pcode)
            except:
                print "Can't load patient", pcode
            else:
                for region in regions:
                    aft = p.get_allele_frequency_trajectories(region, cov_min=cov_min)

                    # get patient to subtype map and subset entropy vectors, convert to bits
                    patient_to_subtype = p.map_to_external_reference(region, refname = 'HXB2')
                    subtype_entropy = hxb2.get_entropy_in_patient_region(patient_to_subtype)/np.log(2.0)
                    ancestral = p.get_initial_indices(region)[patient_to_subtype[:,2]]

                    consensus = hxb2.get_consensus_indices_in_patient_region(patient_to_subtype)
                    away_sites = ancestral==consensus
                    consensus_distance.append(1.0-away_sites.mean())
                    aft_mapped = aft[:,:,patient_to_subtype[:,2]]
                    good_ref = good_pos_in_reference[patient_to_subtype[:,0]]
                    print pcode, region, "dist:",1-away_sites.mean(), "useful_ref:",good_ref.mean()

                    entropy_quantiles = get_quantiles(4, subtype_entropy)
                    # loop over times and calculate the af in entropy bins
                    for t, af in izip(p.dsi,aft):
                        good_af = (((~np.any(af.mask, axis=0))
                                    #&(aft[0].max(axis=0)>0.9)
                                    &(af.argmax(axis=0)<4))[patient_to_subtype[:,2]]) \
                                    & good_ref
                        clean_af = af[:,patient_to_subtype[:,2]][:5,good_af]
                        clean_away = away_sites[good_af]
                        clean_ancestral = ancestral[good_af]
                        clean_entropy = subtype_entropy[good_af]
                        clean_minor = clean_af.sum(axis=0) - clean_af.max(axis=0)
                        clean_derived = clean_af.sum(axis=0) - clean_af[clean_ancestral,np.arange(clean_ancestral.shape[0])]
                        print pcode, region, t, clean_minor[(clean_away)&(clean_entropy<0.1)].mean(),\
                                                clean_minor[(~clean_away)&(clean_entropy<0.1)] 
                        for S,af_minor, af_derived, away in izip(clean_entropy,clean_minor,
                                                                 clean_derived,clean_away):
                            minor_variants.append({'pcode':pcode,'region':region,'time':t,
                                                'S':S, 'af_minor':af_minor, 
                                                'af_derived':af_derived, 'away':away})

        to_away_divergence = []
        # determine genome wide fraction of alleles above a threshold
        for pi, pcode in enumerate(patients):
            try:
                p = Patient.load(pcode)
            except:
                print "Can't load patient", pcode
            else:
                for region in regions:
                    aft = p.get_allele_frequency_trajectories(region, cov_min=cov_min)

                    # get patient to subtype map and subset entropy vectors
                    patient_to_subtype = p.map_to_external_reference(region, refname = 'HXB2')
                    ancestral = p.get_initial_indices(region)[patient_to_subtype[:,2]]

                    consensus = hxb2.get_consensus_indices_in_patient_region(patient_to_subtype)
                    away_sites = ancestral==consensus
                    good_ref = good_pos_in_reference[patient_to_subtype[:,0]]
                    print pcode, region, "dist:",1-away_sites.mean(), "useful_ref:",good_ref.mean()

                    # loop over times and calculate the correlation for each value
                    for t, af in izip(p.dsi,aft):
                        good_af = (((~np.any(af.mask, axis=0))
                                    #&(aft[0].max(axis=0)>0.9)
                                   &(af.argmax(axis=0)<4))[patient_to_subtype[:,2]]) \
                                   & good_ref
                        clean_af = af[:,patient_to_subtype[:,2]][:5,good_af]
                        clean_away = away_sites[good_af]
                        clean_ancestral = ancestral[good_af]
                        clean_consensus = consensus[good_af]
                        clean_reversion = clean_af[clean_consensus,np.arange(clean_consensus.shape[0])]*(~clean_away)
                        clean_total_divergence = clean_af.sum(axis=0) - clean_af[clean_ancestral,np.arange(clean_ancestral.shape[0])]
                        for rev_div, total_div in izip(clean_reversion,clean_total_divergence):
                            to_away_divergence.append({'pcode':pcode,'region':region,'time':t,
                                                'reversion':rev_div, 
                                                'divergence':total_div})


        data={'minor_variants': pd.DataFrame(minor_variants), 
              'to_away':pd.DataFrame(to_away_divergence), 
              'consensus_distance':consensus_distance, 
              'regions':regions, 'patients':patients}
        store_data(data, fn_data)
    else:
        print("Loading data from file")
        data = load_data(fn_data)

plot_to_away(data, fig_filename=foldername+'to_away')
#
