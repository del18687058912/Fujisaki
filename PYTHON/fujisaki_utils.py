import amfm_decompy.pYAAPT as pyaapt
import amfm_decompy.basic_tools as basic
import numpy as np
import fujisaki_model as fm
import matplotlib.pyplot as plt
import utils
import shlex
import subprocess, os, sys, getopt

def generate_fujisaki_params(min_Fb = 20, max_Fb = 500, min_a = 0.0, max_a = 10.0,min_b = 0.0, max_b = 40.0,min_I = 1, max_I = 10, min_J = 1, max_J = 10, verbose = True):

    Fb = np.random.random()*max_Fb
    a = min_a + np.random.random()*(max_a-min_a)
    b = min_b + np.random.random()*(max_b-min_b)
    y = np.random.random()

    # Phrase command number
    I = np.random.randint(min_I, max_I)
    Ap = [0.5]*I - np.random.rand(I)
    T0p = np.random.rand(I)
    T0p.sort()

    # Accent command number
    J = np.random.randint(min_J, max_J)
    Aa = np.random.rand(J)/2
    t = np.random.rand(2*J)
    t.sort()
    T1a = t[0:2*J:2]
    T2a = t[1:2*J:2]

    # Scale command timings with signal length
    # num_samples = time/fs
    # T0p = T0p*num_samples
    # T1a = T1a*num_samples
    # T2a = T2a*num_samples

    if verbose:
        print "Fujisaki parameters:\n" \
              "Fb = {}\n" \
              "a = {}\n" \
              "b = {}\n" \
              "y = {}\n" \
              "I = {}\n" \
              "Ap = {}\n" \
              "T0p = {}\n" \
              "J = {}\n" \
              "Aa = {}\n" \
              "T1a = {}\n" \
              "T2a = {}".format(Fb, a, b, y, I, Ap, T0p, J, Aa, T1a, T2a)
    # Create dict and return it
    p = {}
    for i in ('Fb', 'a', 'b', 'y', 'I', 'J', 'Ap', 'T0p', 'Aa', 'T1a', 'T2a'):
        p[i] = locals()[i]
    return p


def generate_fujisaki_curve(**kwargs):
    # Parse params
    p = kwargs
    show = p.get('show', True)
    verbose = p.get('verbose', False)
    time = p.get('time', 5.0)
    fs = p.get('fs', 20000)

    Fb = p['Fb']
    a = p['a']
    b = p['b']
    y = p['y']
    I = p['I']
    J = p['J']
    Ap = p['Ap']
    T0p = p['T0p']
    Aa = p['Aa']
    T1a = p['T1a']
    T2a = p['T2a']

    # Create time array
    num_samples = int(time*fs)
    x = np.linspace(0, time, num_samples)
    # Scale timings
    T0p = [ti*time for ti in T0p]
    T1a = [ti*time for ti in T1a]
    T2a = [ti*time for ti in T2a]

    # Base frequency component
    y_b = [np.log(Fb)]*num_samples
    # Phrase command components
    Cp = [Ap[i]*fm.calc_Gp(a, x - T0p[i]) for i in range(I)]
    # Accent command components
    Ca = [Aa[j]*(np.subtract(fm.calc_Ga(b, y, x - T1a[j]), fm.calc_Ga(b, y, x - T2a[j]))) for j in range(J)]

    Cp_sum = [sum(cp) for cp in zip(*Cp)] if I != 0 else [0.0]*num_samples
    Ca_sum = [sum(ca) for ca in zip(*Ca)] if J != 0 else [0.0]*num_samples

    y = [sum(comp) for comp in zip(y_b, Ca_sum, Cp_sum)]

    if verbose == True:
        print sum(Cp_sum)
        print len(Cp_sum)
        print sum(Ca_sum)
        print len(Ca_sum)

    if show == True:
        plt.plot(x, y, linewidth=2.0, label='output')
        plt.plot(x, y_b, linestyle='--', label='base comp')
        plt.plot(x, Cp_sum, linestyle='--', label='phrase comp')
        plt.plot(x, Ca_sum, linestyle='--', label='accent comp')
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        plt.show()
    return {'x': x,
            'y': y,
            'Ca': Ca,
            'Cp': Cp,
            'y_b': y_b}


def convert_wav_to_f0_ascii(fname, directory=''):
    # Create the signal object.
    signal = basic.SignalObj(fname)
    # Get time interval and num_samples
    t_start = 0.0
    num_samples = signal.size
    t_end = num_samples / signal.fs
    t = np.linspace(t_start, t_end, num_samples)
    # Create the pitch object and calculate its attributes.
    pitch = pyaapt.yaapt(signal)
    # Create .f0_ascii file and dump f0 to it
    output_fname = directory+os.path.splitext(os.path.basename(fname))[0]+'.f0_ascii'
    with open(output_fname, 'wb') as f:
        for i in range(pitch.nframes):
            f0 = pitch.samp_values[i]
            vu = 1.0 if pitch.vuv[i] else 0.0
            fe = pitch.energy[i] * pitch.mean_energy
            line = '{} {} {} {}\n'.format(f0, vu, fe, vu)
            f.write(line)


def convert_f0_ascii_to_pac(fname, autofuji_fname, directory=''):
    thresh = 0.0001
    min_delta = 100.0
    best_alpha = 1.0
    # Call autofuji.exe for every alpha and check for the min delta
    for alpha in np.linspace(1.0, 3.0, 20):
        args = "{} 0 4 {} auto {}".format(directory + fname, thresh, alpha)
        list_args = shlex.split(autofuji_fname + " " + args)
        output = subprocess.check_output(list_args)
        delta_str = output.splitlines()[-1]
        delta = float(delta_str.split()[-1])
        if delta < min_delta:
            min_delta = delta
            best_alpha = alpha
    args = "{} 0 4 {} auto {}".format(directory + fname, thresh, best_alpha)
    subprocess.call(autofuji_fname + " " + args)


def parse_pac_file(fname):
    with open(fname, 'r') as f:
        lines = f.readlines()
        I = int(lines[7])
        J = int(lines[8])
        Fb = float(lines[9])
        # Parse phrase components
        T0p = []
        Ap = []
        for i in range(20, 20+I):
            t0p, _, ap, a = lines[i].split()
            T0p.append(float(t0p))
            Ap.append(float(ap))

        # Parse accent components
        T1a = []
        T2a = []
        Aa = []
        for i in range(20 + I, 20 + I + J):
            t1a, t2a, aa, b = lines[i].split()
            T1a.append(float(t1a))
            T2a.append(float(t2a))
            Aa.append(float(aa))

        return {'Fb': Fb, 'a': a, 'b': b, 'I': I, 'J': J, 'Ap': Ap, 'T0p': T0p, 'Aa': Aa, 'T1a': T1a, 'T2a': T2a}


def main(argv):

    directory = r'C:/Users/s3628075/Study/Fujisaki/DataBase/'
    autofuji_fname = r'C:/Users/s3628075/Study/Fujisaki_estimator/Autofuji.exe'
    key = 0

    try:
        opts, args = getopt.getopt(argv,"hd:k:",["directory=","key="])
    except getopt.GetoptError:
        print 'fujisaki_utils.py -d <directory> -k <key>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'fujisaki_utils.py -d <directory> -k <key>\n' \
                  '-d <directory>: directory to look up\n' \
                  '-k <key>: operation to perform\n' \
                  '0 - all\n' \
                  '1 - wav to f0_ascii\n' \
                  '2 - f0_ascii to pac'
            sys.exit()
        elif opt in ("-d", "--directory"):
            directory = arg
        elif opt in ("-k", "--key"):
            key = int(arg)
    print 'Working directory is ', directory
    print 'Key is', key
    if key == 0 or key == 1:
        print '//////////////////////////////////////////////////////////\n' \
              'Convert wav files to f0_ascii in', directory
        wav_fnames = utils.get_file_list(directory)
        for fname in wav_fnames:
            print 'convert ', fname
            convert_wav_to_f0_ascii(directory+fname, directory)
        print 'Conversion wav files to f0_ascii finished'

    if key == 0 or key == 2:
        print '//////////////////////////////////////////////////////////\n' \
              'Convert f0_ascii to PAC in', directory

        f0_fnames = utils.get_file_list(directory, '.f0_ascii')
        for fname in f0_fnames:
            convert_f0_ascii_to_pac(fname, autofuji_fname, directory)
        print 'Conversion f0_ascii to PAC finished'

    if key == 0 or key == 3:
        print '/////////////////////////////////////////////////////////\n' \
              'Create report for all .Pac files in ', directory
        pac_fnames = utils.get_file_list(directory, '.PAC')
        p_all = {}
        with open(directory+'Report.rep', 'w') as f:
            for fname in pac_fnames:
                params = parse_pac_file(directory+fname)
                f.write('{} {}\n'.format(fname, params))
                p_all[fname] = params
        utils.save_obj(p_all, 'Report', directory)
        print 'Report.rep created in ', directory

    print '//////////////////////////////////////////////////////////\n' \
          '/////////////////////// Finish ///////////////////////////\n' \
          '//////////////////////////////////////////////////////////'
if __name__ == "__main__":
   main(sys.argv[1:])