
import ned.IdealChannel;

network topology
{
    submodules:
gas_1_1: DistributionStation { }
gas_1_4: DistributionStation { }
gas_1_6: DistributionStation { }
gas_1_17: DistributionStation { }
gas_1_8: DistributionStation { }
gas_2_1: DistributionStation { }
gas_1_7: DistributionStation { }
gas_1_9: DistributionStation { }
gas_1_10: DistributionStation { }
valve1: Valve { }
valve4: Valve { }
valve10: Valve { }
valve9: Valve { }
gas9: GasFlowSink { }
gas10: GasFlowSink { }
gas1: GasFlowSink { }
gas4: GasFlowSink { }
valve21: Valve { }
gas21: GasFlowSink { }
receivingStationInput: ReceivingStationInput { }
    connections:
gas_1_1.out++ --> GasPipe { 
diameter = 600.0;
wallThickness = 9.5;
heatTransferCoefficient = 52.0;
Length = 12.845k;
ValveInitialOpening = 1.0;
elevationChange = 4.0;
T = 296.15K;
epsilon = 0.045;
delta = 0.6106;
z = 0.95;
} --> gas_1_4.in++;
gas_2_1.out++ --> GasPipe { 
diameter = 750.0;
wallThickness = 9.5;
heatTransferCoefficient = 52.0;
Length = 11.975k;
ValveInitialOpening = 1.0;
elevationChange = 14.0;
T = 296.15K;
epsilon = 0.045;
delta = 0.6106;
z = 0.95;
} --> gas_1_8.in++;
gas_2_1.out++ --> GasPipe { 
diameter = 400.0;
wallThickness = 9.5;
heatTransferCoefficient = 52.0;
Length = 17.9k;
ValveInitialOpening = 1.0;
elevationChange = 5.0;
T = 296.15K;
epsilon = 0.045;
delta = 0.6106;
z = 0.95;
} --> gas_1_6.in++;
gas_2_1.out++ --> GasPipe { 
diameter = 400.0;
wallThickness = 9.5;
heatTransferCoefficient = 52.0;
Length = 17.279k;
ValveInitialOpening = 1.0;
elevationChange = 5.0;
T = 296.15K;
epsilon = 0.045;
delta = 0.6106;
z = 0.95;
} --> gas_1_17.in++;
gas_1_8.out++ --> GasPipe { 
diameter = 600.0;
wallThickness = 9.5;
heatTransferCoefficient = 52.0;
Length = 7.840k;
ValveInitialOpening = 1.0;
elevationChange = 2.0;
T = 296.15K;
epsilon = 0.045;
delta = 0.6106;
z = 0.95;
} --> gas_1_7.in++;
gas_1_7.out++ --> GasPipe { 
diameter = 400.0;
wallThickness = 9.5;
heatTransferCoefficient = 52.0;
Length = 10.042k;
ValveInitialOpening = 1.0;
elevationChange = 5.0;
T = 296.15K;
epsilon = 0.045;
delta = 0.6106;
z = 0.95;
} --> gas_1_1.in++;
gas_1_6.out++ --> GasPipe { 
diameter = 400.0;
wallThickness = 9.5;
heatTransferCoefficient = 52.0;
Length = 20k;
ValveInitialOpening = 1.0;
elevationChange = 5.0;
T = 296.15K;
epsilon = 0.045;
delta = 0.6106;
z = 0.95;
} --> gas_1_9.in++;
gas_1_17.out++ --> GasPipe { 
diameter = 400.0;
wallThickness = 9.5;
heatTransferCoefficient = 52.0;
Length = 80k;
ValveInitialOpening = 1.0;
elevationChange = 5.0;
T = 296.15K;
epsilon = 0.045;
delta = 0.6106;
z = 0.95;
} --> gas_1_10.in++;
}