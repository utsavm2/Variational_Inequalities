from functools import partial

import numpy as np

from VISolver.Projection import IdentityProjection
from VISolver.Solver import Solver
from VISolver.Utilities import GramSchmidt, Jv, Jv_num


class HeunEuler_LEGS(Solver):

    def __init__(self, Domain, P=IdentityProjection(), Delta0=1e-2,
                 GrowthLimit=2, MinStep=-1e10, MaxStep=1e10, NTopLEs=None):

        self.F = Domain.F

        try:
            self.Jv = partial(Jv,Jac=Domain.Jac)
        except AttributeError:
            self.Jv = partial(Jv_num,F=self.F)

        self.Proj = P

        self.StorageSize = 1

        self.TempStorage = {}

        self.Delta0 = Delta0

        self.GrowthLimit = GrowthLimit

        self.MinStep = MinStep

        self.MaxStep = MaxStep

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

        self.TempStorage['Step'] = self.StorageSize*[Options.Init.Step]
        self.TempStorage['F Evaluations'] = self.StorageSize*[1]
        self.TempStorage['Projections'] = self.StorageSize*[0]

        return self.TempStorage

    # BookKeeping(self,TempData) defined in super class 'Solver'

    def Update(self,Record):

        # Retrieve Necessary Data
        Data_x = Record.TempStorage['Data'][-1]
        Data_psi = Record.TempStorage['Psi'][-1]
        Lyapunov = Record.TempStorage['Lyapunov'][-1]
        T = Record.TempStorage['T'][-1]
        dim = Data_x.size

        Fs_x = np.zeros((2,Data_x.shape[0]),dtype=Data_x.dtype)
        Fs_x[0,:] = Record.TempStorage[self.F][-1]

        Fs_psi = np.zeros((2,Data_psi.shape[0]),dtype=Data_psi.dtype)
        Fs_psi[0,:] = Record.TempStorage['dPsi'][-1]

        Step = Record.TempStorage['Step'][-1]

        # Initialize Storage
        TempData = {}

        # Perform Update
        _NewData_x = self.Proj.P(Data_x,Step,Fs_x[0,:])
        _NewData_psi = Data_psi+Step*Fs_psi[0,:]

        Fs_x[1,:] = self.F(_NewData_x)
        Fs_psi[1,:] = self.Jv(_NewData_x,_NewData_psi,F_Data=Fs_x[1,:]).flatten()

        NewData_x = self.Proj.P(Data_x,Step,0.5*np.sum(Fs_x,axis=0))
        NewData_psi = Data_psi+Step*0.5*np.sum(Fs_psi,axis=0)

        # Compute Deltas
        Delta_x = max(abs(NewData_x-_NewData_x))
        Delta_psi = max(abs(NewData_psi-_NewData_psi))

        # Orthogonalize Psi, Record Lyapunov Exponents, Normalize Psi
        NewData_psi = NewData_psi.reshape((dim,-1))
        NewData_psi = GramSchmidt(NewData_psi,normalize=False)
        LEDT = np.log(np.linalg.norm(NewData_psi,axis=0))
        Tnew = T + abs(Step)
        NewLyapunov = (Lyapunov*T+LEDT)/Tnew
        NewData_psi = NewData_psi/np.linalg.norm(NewData_psi,axis=0)

        # Adjust Stepsize
        Delta = max(Delta_x,Delta_psi)
        if Delta == 0:
            growth = self.GrowthLimit
        else:
            growth = min((self.Delta0/Delta)**0.5, self.GrowthLimit)
        Step = np.clip(growth*Step,self.MinStep,self.MaxStep)

        # Store Data
        TempData['Data'] = NewData_x
        TempData[self.F] = self.F(NewData_x)
        TempData['Psi'] = NewData_psi.flatten()
        TempData['dPsi'] = self.Jv(NewData_x,NewData_psi,F_Data=TempData[self.F]).flatten()
        TempData['Lyapunov'] = NewLyapunov
        TempData['T'] = Tnew
        TempData['Step'] = Step
        TempData['F Evaluations'] = 2 + self.TempStorage['F Evaluations'][-1]
        TempData['Projections'] = 2 + self.TempStorage['Projections'][-1]
        self.BookKeeping(TempData)

        return self.TempStorage
