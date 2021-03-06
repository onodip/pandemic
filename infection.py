import numpy as np
import openmdao.api as om

def KS(g, rho=50.0):
    """
    Kreisselmeier-Steinhauser constraint aggregation function.
    """
    g_max = np.max(np.atleast_2d(g), axis=-1)[:, np.newaxis]
    g_diff = g - g_max
    exponents = np.exp(rho * g_diff)
    summation = np.sum(exponents, axis=-1)[:, np.newaxis]

    KS = g_max + 1.0 / rho * np.log(summation)

    dsum_dg = rho * exponents
    dKS_dsum = 1.0 / (rho * summation)
    dKS_dg = dKS_dsum * dsum_dg

    dsum_drho = np.sum(g_diff * exponents, axis=-1)[:, np.newaxis]
    dKS_drho = dKS_dsum * dsum_drho

    return KS, dKS_dg.flatten()

class Infection(om.ExplicitComponent):

    def initialize(self):
        self.options.declare('num_nodes', types=int)

    def setup(self):
        nn = self.options['num_nodes']

        # States
        self.add_input('S',
                       val=np.zeros(nn))

        self.add_input('E',
                       val=np.zeros(nn))

        self.add_input('I',
                       val=np.zeros(nn))

        self.add_input('R',
                       val=np.zeros(nn))

        self.add_input('D',
                       val=np.zeros(nn))

        # ROCs
        self.add_output('Sdot', val=np.zeros(nn))
        self.add_output('Edot', val=np.zeros(nn))
        self.add_output('Idot', val=np.zeros(nn))
        self.add_output('Rdot', val=np.zeros(nn))
        self.add_output('Ddot', val=np.zeros(nn))

        # Params
        self.add_input('alpha',
                       val = np.zeros(nn))

        self.add_input('beta',
                       val = np.zeros(nn))

        self.add_input('sigma',
                       val = np.zeros(nn))

        self.add_input('gamma',
                       val = np.zeros(nn))

        self.add_input('epsilon',
                       val = np.zeros(nn))

        self.add_input('mu',
                       val = np.zeros(nn))

        self.add_input('t',
                       val = np.zeros(nn))

        self.add_input('a',
                       val=5.0,
                       desc='scale parameter')
        self.add_input('t_on',
                       val=20.0,
                       desc='trigger time')
        self.add_input('t_off',
                       val=60.0,
                       desc='trigger time')

        self.add_output('theta',
                       val=np.zeros(nn))
        self.add_output('max_I', 0.0)

        self.add_output('sigma_sq', np.zeros(nn))

        arange = np.arange(self.options['num_nodes'], dtype=int)

        self.declare_partials('Sdot', ['beta', 'sigma', 'epsilon', 'S', 'I', 'R', 't'], rows=arange, cols=arange)
        self.declare_partials('Sdot', ['a', 't_on', 't_off'])

        self.declare_partials('Edot', ['beta', 'sigma', 'S', 'E', 'I', 't', 'alpha'], rows=arange, cols=arange)
        self.declare_partials('Edot', ['a', 't_on', 't_off'])

        self.declare_partials('Idot', ['gamma', 'E', 'I', 'alpha', 'mu'], rows=arange, cols=arange)
        self.declare_partials('Rdot', ['gamma', 'epsilon', 'I', 'R'], rows=arange, cols=arange)

        self.declare_partials('Ddot', ['mu', 'I'], rows=arange, cols=arange)

        self.declare_partials('theta', ['beta', 'sigma', 't'], rows=arange, cols=arange)
        self.declare_partials('theta', ['a', 't_on', 't_off'])

        self.declare_partials('sigma_sq', ['sigma'], rows=arange, cols=arange)
        self.declare_partials('max_I', 'I')

    def compute(self, inputs, outputs):
        beta, sigma, mu, epsilon, gamma, S, E, I, R, a, t_on, t_off, t, alpha = inputs['beta'], inputs['sigma'], inputs['mu'], inputs['epsilon'], inputs['gamma'], inputs['S'], inputs['E'], inputs['I'], inputs['R'], inputs['a'], inputs['t_on'], inputs['t_off'], inputs['t'], inputs['alpha']
        
        # determine a cut-off where the infection is gone
        I[np.where(I < 1e-4)] = 0.0
        #E[np.where(E < 1e-6)] = 0.0

        # fix numerical overflow
        d_ton = np.exp(-a*(t - t_on))
        d_toff = np.exp(-a*(-t + t_off))

        d_ton[np.where(d_ton > 1.e10)] = 1.e10
        d_toff[np.where(d_toff > 1.e10)] = 1.e10

        y = 1 / (1 + d_ton) * 1 / (1 + d_toff) 

        theta = (beta - sigma)*y + (1 - y) * beta

        agg_i, self.dagg_i = KS(I)
        outputs['max_I'] = np.sum(agg_i)

        outputs['sigma_sq'] = sigma**2

        outputs['theta'] = theta

        outputs['Sdot'] = -theta * S * I + epsilon * R
        outputs['Edot'] = theta * S * I - alpha * E
        outputs['Idot'] = alpha * E - gamma * I - mu * I
        outputs['Rdot'] = gamma * I - epsilon * R
        outputs['Ddot'] = mu * I

    def compute_partials(self, inputs, jacobian):
        beta, sigma, mu, epsilon, gamma, S, E, I, R, a, t_on, t_off, t, alpha = inputs['beta'], inputs['sigma'], inputs['mu'], inputs['epsilon'], inputs['gamma'], inputs['S'], inputs['E'], inputs['I'], inputs['R'], inputs['a'], inputs['t_on'], inputs['t_off'], inputs['t'], inputs['alpha']
        
        # determine a cut-off where the infection is gone
        I[np.where(I < 1e-4)] = 0.0
        #E[np.where(E < 1e-6)] = 0.0

        # fix numerical overflow
        d_ton = np.exp(-a*(t - t_on))
        d_toff = np.exp(-a*(-t + t_off))

        d_ton[np.where(d_ton > 1.e10)] = 1.e10
        d_toff[np.where(d_toff > 1.e10)] = 1.e10

        jacobian['Sdot', 'beta'] = -I*S
        jacobian['Sdot', 'sigma'] = I*S/((1 + d_toff)*(1 + d_ton))
        jacobian['Sdot', 'epsilon'] = R
        jacobian['Sdot', 'S'] = I*(-beta*(1 - 1/((1 + d_toff)*(1 + d_ton))) - (beta - sigma)/((1 + d_toff)*(1 + d_ton)))
        jacobian['Sdot', 'I'] = S*(-beta*(1 - 1/((1 + d_toff)*(1 + d_ton))) - (beta - sigma)/((1 + d_toff)*(1 + d_ton)))
        jacobian['Sdot', 'R'] = epsilon
        jacobian['Sdot', 'a'] = I*S*(-beta*((-t + t_on)*d_ton/((1 + d_toff)*(1 + d_ton)**2) + (t - t_off)*d_toff/((1 + d_toff)**2*(1 + d_ton))) + (beta - sigma)*(-t + t_on)*d_ton/((1 + d_toff)*(1 + d_ton)**2) + (beta - sigma)*(t - t_off)*d_toff/((1 + d_toff)**2*(1 + d_ton)))
        jacobian['Sdot', 't_on'] = I*S*(-a*beta*d_ton/((1 + d_toff)*(1 + d_ton)**2) + a*(beta - sigma)*d_ton/((1 + d_toff)*(1 + d_ton)**2))
        jacobian['Sdot', 't_off'] = I*S*(a*beta*d_toff/((1 + d_toff)**2*(1 + d_ton)) - a*(beta - sigma)*d_toff/((1 + d_toff)**2*(1 + d_ton)))
        jacobian['Sdot', 't'] = I*S*(-a*(beta - sigma)*d_ton/((1 + d_toff)*(1 + d_ton)**2) + a*(beta - sigma)*d_toff/((1 + d_toff)**2*(1 + d_ton)) - beta*(-a*d_ton/((1 + d_toff)*(1 + d_ton)**2) + a*d_toff/((1 + d_toff)**2*(1 + d_ton))))

        jacobian['Edot', 'beta'] = I*S
        jacobian['Edot', 'sigma'] = -I*S/((1 + d_toff)*(1 + d_ton))
        jacobian['Edot', 'S'] = I*(beta*(1 - 1/((1 + d_toff)*(1 + d_ton))) + (beta - sigma)/((1 + d_toff)*(1 + d_ton)))
        jacobian['Edot', 'E'] = -alpha
        jacobian['Edot', 'I'] = S*(beta*(1 - 1/((1 + d_toff)*(1 + d_ton))) + (beta - sigma)/((1 + d_toff)*(1 + d_ton)))
        jacobian['Edot', 'a'] = I*S*(beta*((-t + t_on)*d_ton/((1 + d_toff)*(1 + d_ton)**2) + (t - t_off)*d_toff/((1 + d_toff)**2*(1 + d_ton))) - (beta - sigma)*(-t + t_on)*d_ton/((1 + d_toff)*(1 + d_ton)**2) - (beta - sigma)*(t - t_off)*d_toff/((1 + d_toff)**2*(1 + d_ton)))
        jacobian['Edot', 't_on'] = I*S*(a*beta*d_ton/((1 + d_toff)*(1 + d_ton)**2) - a*(beta - sigma)*d_ton/((1 + d_toff)*(1 + d_ton)**2))
        jacobian['Edot', 't_off'] = I*S*(-a*beta*d_toff/((1 + d_toff)**2*(1 + d_ton)) + a*(beta - sigma)*d_toff/((1 + d_toff)**2*(1 + d_ton)))
        jacobian['Edot', 't'] = I*S*(a*(beta - sigma)*d_ton/((1 + d_toff)*(1 + d_ton)**2) - a*(beta - sigma)*d_toff/((1 + d_toff)**2*(1 + d_ton)) + beta*(-a*d_ton/((1 + d_toff)*(1 + d_ton)**2) + a*d_toff/((1 + d_toff)**2*(1 + d_ton))))
        jacobian['Edot', 'alpha'] = -E

        jacobian['Idot', 'mu'] = -I
        jacobian['Idot', 'gamma'] = -I
        jacobian['Idot', 'E'] = alpha
        jacobian['Idot', 'I'] = -gamma - mu
        jacobian['Idot', 'alpha'] = E

        jacobian['Rdot', 'gamma'] = I
        jacobian['Rdot', 'epsilon'] = -R
        jacobian['Rdot', 'I'] = gamma
        jacobian['Rdot', 'R'] = -epsilon

        jacobian['Ddot', 'mu'] = I
        jacobian['Ddot', 'I'] = mu


        jacobian['theta', 'beta'] = 1.0
        jacobian['theta', 'sigma'] = -1/((1 + d_toff)*(1 + d_ton))
        jacobian['theta', 'a'] = beta*((-t + t_on)*d_ton/((1 + d_toff)*(1 + d_ton)**2) + (t - t_off)*d_toff/((1 + d_toff)**2*(1 + d_ton))) - (beta - sigma)*(-t + t_on)*d_ton/((1 + d_toff)*(1 + d_ton)**2) - (beta - sigma)*(t - t_off)*d_toff/((1 + d_toff)**2*(1 + d_ton))
        jacobian['theta', 't_on'] = a*beta*d_ton/((1 + d_toff)*(1 + d_ton)**2) - a*(beta - sigma)*d_ton/((1 + d_toff)*(1 + d_ton)**2)
        jacobian['theta', 't_off'] = -a*beta*d_toff/((1 + d_toff)**2*(1 + d_ton)) + a*(beta - sigma)*d_toff/((1 + d_toff)**2*(1 + d_ton))
        jacobian['theta', 't'] = a*(beta - sigma)*d_ton/((1 + d_toff)*(1 + d_ton)**2) - a*(beta - sigma)*d_toff/((1 + d_toff)**2*(1 + d_ton)) + beta*(-a*d_ton/((1 + d_toff)*(1 + d_ton)**2) + a*d_toff/((1 + d_toff)**2*(1 + d_ton)))

        jacobian['max_I', 'I'] = self.dagg_i

        jacobian['sigma_sq', 'sigma'] = 2.0 * sigma

if __name__ == '__main__':
  
  p = om.Problem()
  p.model = om.Group()
  n = 35
  p.model.add_subsystem('test', Infection(num_nodes=n), promotes=['*'])
  p.setup(force_alloc_complex=True)
  np.random.seed(0)
  p['S'] = np.random.uniform(1, 1000, n)
  p['E'] = np.random.uniform(1, 1000, n)
  p['I'] = np.random.uniform(1, 1000, n)
  p['R'] = np.random.uniform(1, 1000, n)
  p['D'] = np.random.uniform(1, 1000, n)

  p['beta'] = np.random.uniform(0, 2, n)
  p['sigma'] = np.random.uniform(0, 2, n)
  p['gamma'] = np.random.uniform(0, 2, n)
  p['t'] = np.linspace(0, 100, n)
  p.run_model()
  p.check_partials(compact_print=True, method='cs')

  print(np.max(p['I']), p['max_I'])
