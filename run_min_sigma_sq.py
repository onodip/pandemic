import numpy as np
import openmdao.api as om
import dymos as dm
import matplotlib.pyplot as plt

from infection import Infection

pop_total = 1.0
infected0 = 1 / 500.0
ns = 50

p = om.Problem(model=om.Group())

traj = dm.Trajectory()

p.model.add_subsystem('traj', subsys=traj)

phase = dm.Phase(ode_class=Infection,
                 transcription=dm.GaussLobatto(num_segments=ns, 
                                               order=3))
p.model.linear_solver = om.DirectSolver()
phase.set_time_options(fix_initial=True, duration_bounds=(200.0, 301.0), targets=['t'])
#phase.set_time_options(fix_initial=True, fix_duration=True)


ds = 1e-1
phase.add_state('S', fix_initial=True, rate_source='Sdot', targets=['S'], lower=0.0,
                upper=pop_total, ref=pop_total/2, defect_scaler = ds)
phase.add_state('E', fix_initial=True, rate_source='Edot', targets=['E'], lower=0.0,
                upper=pop_total, ref=pop_total/2, defect_scaler = ds)
phase.add_state('I', fix_initial=True, rate_source='Idot', targets=['I'], lower=0.0,
                upper=pop_total, ref=pop_total/2, defect_scaler = ds)
phase.add_state('R', fix_initial=True, rate_source='Rdot', targets=['R'], lower=0.0,
                upper=pop_total, ref=pop_total/2, defect_scaler = ds)
phase.add_state('int_sigma', rate_source='sigma_sq', lower=0.0, defect_scaler = 1e-2)

#p.driver = om.ScipyOptimizeDriver()

p.driver = om.pyOptSparseDriver()
p.driver.options['optimizer'] = 'SNOPT'
#p.driver.opt_settings['Major feasibility tolerance'] = 1.0E-8
#p.driver.opt_settings['Major optimality tolerance'] = 1.0E-5
p.driver.opt_settings['iSumm'] = 6

p.driver.declare_coloring()


beta = 0.25
gamma = 1.0 / 14.0
alpha = 1.0 / 5.0
epsilon = 1.0 / 365.
lim = 0.15

phase.add_input_parameter('alpha', targets=['alpha'], dynamic=True, val=alpha)
phase.add_input_parameter('beta', targets=['beta'], dynamic=True, val=beta)
phase.add_input_parameter('gamma', targets=['gamma'], dynamic=True, val=gamma)
phase.add_input_parameter('epsilon', targets=['epsilon'], dynamic=True, val=epsilon)

t_on, t_off = 20.0, 500.0
phase.add_input_parameter('t_on', targets=['t_on'], dynamic=False, val=t_on)
phase.add_input_parameter('t_off', targets=['t_off'], dynamic=False, val=t_off)

# constant control
#phase.add_input_parameter('sigma', targets=['sigma'], dynamic=True, val=beta)

# polynomial control
#phase.add_polynomial_control('sigma', targets=['sigma'], lower=0.0, upper=0.2, ref=0.1, order=1)

# adaptive control
phase.add_control('sigma', targets=['sigma'], lower=0.0, upper=beta)

# run out the pandemic
phase.add_boundary_constraint('E', loc='final', upper=1e-6)

# put a ceiling on the infection
phase.add_path_constraint('I', upper=lim)

# minimize net mitigation
phase.add_objective('int_sigma', loc='final')

phase.add_timeseries_output('theta')


traj.add_phase(name='phase0', phase=phase)
p.setup(check=True)

p.set_val('traj.phase0.t_initial', 0)
p.set_val('traj.phase0.t_duration', 200)

p.set_val('traj.phase0.states:S',
          phase.interpolate(ys=[pop_total - infected0, 0], nodes='state_input'))
p.set_val('traj.phase0.states:E',
          phase.interpolate(ys=[infected0, 0], nodes='state_input'))
p.set_val('traj.phase0.states:I',
          phase.interpolate(ys=[0, pop_total/2], nodes='state_input'))
p.set_val('traj.phase0.states:R',
          phase.interpolate(ys=[0, pop_total/2], nodes='state_input'))


p.run_driver()
sim_out = traj.simulate()

t = sim_out.get_val('traj.phase0.timeseries.time')
s = sim_out.get_val('traj.phase0.timeseries.states:S')
e = sim_out.get_val('traj.phase0.timeseries.states:E')
i = sim_out.get_val('traj.phase0.timeseries.states:I')
r = sim_out.get_val('traj.phase0.timeseries.states:R')

int_sigma = sim_out.get_val('traj.phase0.timeseries.states:int_sigma')
print("objective:", int_sigma[-1])

theta = sim_out.get_val('traj.phase0.timeseries.theta')


fig = plt.figure(figsize=(10, 5))
plt.subplot(211)
plt.title('mitigation starting t = 10.0')
plt.plot(t, len(t)*[lim],'k--', lw=1)
plt.plot(t, s/pop_total, 'orange', lw=2, label='susceptible')
plt.plot(t, e/pop_total, 'k', lw=2, label='exposed')
plt.plot(t, i/pop_total, 'teal', lw=2, label='infected')
plt.plot(t, r/pop_total, 'g', lw=2, label='recovd/immune')
plt.xlabel('days')
plt.ylabel('pct. pop')
plt.legend(loc=1)
plt.subplot(212)
plt.plot(t, len(t)*[beta], lw=2, label='$\\beta$')
plt.plot(t, theta, lw=2, label='$\\theta$(t)')
plt.legend()
plt.show()