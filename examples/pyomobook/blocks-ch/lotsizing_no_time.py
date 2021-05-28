import pyomo.environ as pyo

model = pyo.ConcreteModel()
model.T = pyo.RangeSet(5)    # time periods
model.S = pyo.RangeSet(5)

i0 = 5.0           # initial inventory
c = 4.6            # setup cost
h_pos = 0.7        # inventory holding cost
h_neg = 1.2        # shortage cost
P = 5.0            # maximum production amount

# demand during period t
d = {1: 5.0, 2:7.0, 3:6.2, 4:3.1, 5:1.7}

# @vars:
# define the variables
model.y = pyo.Var(domain=pyo.Binary)
model.x = pyo.Var(domain=pyo.NonNegativeReals)
model.i = pyo.Var()
model.i_pos = pyo.Var(domain=pyo.NonNegativeReals)
model.i_neg = pyo.Var(domain=pyo.NonNegativeReals)
# @:vars

model.pprint()
