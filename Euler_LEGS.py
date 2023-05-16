from functools import partial

import numpy as np

from VISolver.Projection import IdentityProjection
from VISolver.Solver import Solver
from VISolver.Utilities import GramSchmidt, Jv, Jv_num


class Euler_LEGS(Solver):

    def __init__(self, Domain, P=IdentityProjection(), FixStep=False, 
                 NTopLEs=None):

        self.F = Domain.F

        try:
            self.Jv = partial(Jv,Jac=Domain.Jac)
        except AttributeError:
            self.Jv = partial(Jv_num,F=self.F)

        self.Proj = P

        self.FixStep = FixStep

        self.StorageSize = 1

        self.TempStorage = {}

        self.NTopLEs = NTopLEs

    def InitTempStorage(self,Start,Domain,Options):

        self.TempStorage['Data'] = self.StorageSize*[Start]
        self.TempStorage[self.F] = self.StorageSize*[self.F(Start)]

        if self.NTopLEs is None:
            self.NTopLEs = Start.size
            Psi_0 = np.eye(self.NTopLEs)
        else:
            assert self.NTopLEs <= Start.size and self.NTopLEs > 0
            Psi_0 = np.vstack([np.eye(self.NTopLEs),np.zeros((Start.size-self.NTopLEs,self.NTopLEs))])

        dPsi_0 = self.Jv(Start,Psi_0,F_Data=self.TempStorage[self.F][-1])
        self.TempStorage['Psi'] = self.StorageSize*[Psi_0.flatten()]
        self.TempStorage['dPsi'] = self.StorageSize*[dPsi_0.flatten()]
        self.TempStorage['Lyapunov'] = self.StorageSize*[np.zeros(self.NTopLEs)]
        self.TempStorage['T'] = self.StorageSize*[0]

        self.TempStorage['scount'] = self.StorageSize*[0]
        self.TempStorage['s'] = self.StorageSize*[1]
        self.TempStorage['Step'] = self.StorageSize*[Options.Init.Step]
        self.TempStorage['F Evaluations'] = self.StorageSize*[1]
        self.TempStorage['Projections'] = self.StorageSize*[0]

        self.InitStep = Options.Init.Step

        return self.TempStorage

    # BookKeeping(self,TempData) defined in super class 'Solver'

    def Update(self,Record):

        # Retrieve Necessary Data
        Data_x = Record.TempStorage['Data'][-1]
        Data_psi = Record.TempStorage['Psi'][-1]
        Lyapunov = Record.TempStorage['Lyapunov'][-1]
        T = Record.TempStorage['T'][-1]
        dim = Data_x.size

        F_x = Record.TempStorage[self.F][-1]
        F_psi = Record.TempStorage['dPsi'][-1]

        scount = self.TempStorage['scount'][-1]
        s = self.TempStorage['s'][-1]

        if self.FixStep:
            Step = self.InitStep
        else:  # Use Decreasing Step Size Scheme
            if scount >= s:
                scount = 0
                s += 1
            scount += 1
            Step = self.InitStep/s

        # Initialize Storage
        TempData = {}

        # Perform Update
        NewData_x = self.Proj.P(Data_x,Step,F_x)
        NewData_psi = (Data_psi+Step*F_psi).reshape((dim,-1))

        # Orthogonalize Psi, Record Lyapunov Exponents, Normalize Psi
        NewData_psi = GramSchmidt(NewData_psi,normalize=False)
        LEDT = np.log(np.linalg.norm(NewData_psi,axis=0))
        Tnew = T + abs(Step)
        NewLyapunov = (Lyapunov*T+LEDT)/Tnew
        NewData_psi = NewData_psi/np.linalg.norm(NewData_psi,axis=0)

        # Store Data
        TempData['Data'] = NewData_x
        TempData[self.F] = self.F(NewData_x)
        TempData['Psi'] = NewData_psi.flatten()
        TempData['dPsi'] = self.Jv(NewData_x,NewData_psi,F_Data=TempData[self.F]).flatten()
        TempData['Lyapunov'] = NewLyapunov
        TempData['T'] = Tnew
        TempData['scount'] = scount
        TempData['s'] = s
        TempData['Step'] = Step
        TempData['F Evaluations'] = 1 + self.TempStorage['F Evaluations'][-1]
        TempData['Projections'] = 1 + self.TempStorage['Projections'][-1]
        self.BookKeeping(TempData)
        return self.TempStorage
