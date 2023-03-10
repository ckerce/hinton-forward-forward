#
#
#  Invesigating the properties of the forward-forward implementation by Mohammad Pezeshki
#  Original source:
#          https://github.com/mohammadpz/pytorch_forward_forward

import torch
import pdb
import torch.nn as nn
from tqdm import tqdm
from torch.optim import Adam
from torchvision.datasets import MNIST
from torchvision.transforms import Compose, ToTensor, Normalize, Lambda
from torch.utils.data import DataLoader
from random import sample
import matplotlib.pyplot as plt
import numpy as np


def MNIST_loaders(train_batch_size=25000, test_batch_size=30000):

    transform = Compose([
        ToTensor(),
        Normalize((0.1307,), (0.3081,)),
        Lambda(lambda x: torch.flatten(x))])

    train_loader = DataLoader(
        MNIST('./data/', train=True,
              download=True,
              transform=transform),
        batch_size=train_batch_size, shuffle=True)

    test_loader = DataLoader(
        MNIST('./data/', train=False,
              download=True,
              transform=transform),
        batch_size=test_batch_size, shuffle=False)

    return train_loader, test_loader


def overlay_y_on_x(x, y):
    x_ = x.clone()
    #pdb.set_trace()
    x_[:, :10] *= 0.0
    x_[range(x.shape[0]), y] = x.max()
    return x_


class Net(torch.nn.Module):

    def __init__(self, dims):
        super().__init__()
        self.layers = []
        for d in range(len(dims) - 1):
            #self.layers += [Layer(dims[d], dims[d + 1]).cuda()]
            self.layers += [Layer(dims[d], dims[d + 1])]

    def predict(self, x):
        goodness_per_label = []
        for label in range(10):
            h = overlay_y_on_x(x, label)
            goodness = []
            for layer in self.layers:
                h = layer(h)
                goodness += [h.pow(2).mean(1)]
            goodness_per_label += [sum(goodness).unsqueeze(1)]
        goodness_per_label = torch.cat(goodness_per_label, 1)
        return goodness_per_label.argmax(1)

    def train(self, x_pos, x_neg):
        h_pos, h_neg = x_pos, x_neg
        for i, layer in enumerate(self.layers):
            print('training layer', i, '...')
            h_pos, h_neg = layer.train(h_pos, h_neg)


class Layer(nn.Linear):
    def __init__(self, in_features, out_features,
                 bias=True, device=None, dtype=None):
        super().__init__(in_features, out_features, bias, device, dtype)
        self.relu = torch.nn.ReLU()
        self.opt = Adam(self.parameters(), lr=0.03)
        self.threshold = 2.0
        self.num_epochs = 1000
        self.pos = []
        self.neg = []

    def forward(self, x):
        x_direction = x / (x.norm(2, 1, keepdim=True) + 1e-4)
        return self.relu(
            torch.mm(x_direction, self.weight.T) +
            self.bias.unsqueeze(0))

    def train(self, x_pos, x_neg):
        for i in tqdm(range(self.num_epochs)):
            #idxs = torch.randperm(len(x_pos[:,0]))[:1000]
            #g_pos = self.forward(x_pos[idxs,:]).pow(2).mean(1)
            #g_neg = self.forward(x_neg[idxs,:]).pow(2).mean(1)
            g_pos = self.forward(x_pos).pow(2).mean(1)
            g_neg = self.forward(x_neg).pow(2).mean(1)
            # The following loss pushes pos (neg) samples to
            # values larger (smaller) than the self.threshold.
            if i % 100 == 99:
               self.pos.append( g_pos.detach().numpy() )
               self.neg.append( g_neg.detach().numpy() )
            loss = torch.log(1 + torch.exp(torch.cat([
                -g_pos + self.threshold,
                g_neg - self.threshold]))).mean()
            self.opt.zero_grad()
            # this backward just compute the derivative and hence
            # is not considered backpropagation.
            loss.backward()
            self.opt.step()
        return self.forward(x_pos).detach(), self.forward(x_neg).detach()

def clean_up_mem(x):
   x = torch.tensor( x.detach().numpy() )
   return x

def reshape_hist( out ):
   out = ( out[0], 
           0.5 * ( out[1][:-1] + out[1][1:] ) )
   return out

def plot_histograms(net, layeridx, close_histograms=True):
    Xpos = []
    Hpos = []
    Xneg = []
    Hneg = []
    plt.ion()
    for i in range(len(net.layers[layeridx].pos)):
       plt.figure()
       out_pos = plt.hist(net.layers[layeridx].pos[i], 100)
       out_neg = plt.hist(net.layers[layeridx].neg[i], 100)
       if close_histograms:
          plt.close()
    
       out_pos = reshape_hist(out_pos)
       out_neg = reshape_hist(out_neg)
       Xpos.append(out_pos[1])
       Hpos.append(out_pos[0])
       Xneg.append(out_neg[1])
       Hneg.append(out_neg[0])

    Xpos = np.array(Xpos).transpose() 
    Hpos = np.array(Hpos).transpose() 
    Xneg = np.array(Xneg).transpose() 
    Hneg = np.array(Hneg).transpose() 

    plt.figure()
    for idx in range( Xpos.shape[1]):
       plt.plot(Xpos[:,idx] + 10*idx, Hpos[:,idx], 'k', Xneg[:,idx] + 10*idx, Hneg[:,idx], 'k--')

    plt.legend(['Positive Examples', 'Negative Examples'])
    plt.grid('on')

if __name__ == "__main__":
    torch.manual_seed(1234)
    train_loader, test_loader = MNIST_loaders()

    net = Net([784, 500, 500, 500])
    x, y = next(iter(train_loader))
    #x, y = x.cuda(), y.cuda()
    x, y = x, y
    x_pos = overlay_y_on_x(x, y)
    rnd = torch.randperm(x.size(0))
    yn = y[rnd]
    ind = y != yn
    x_pos = x_pos[ind,:]
    x_pos = clean_up_mem( x_pos )    

    x = x[ind, :]
    x = clean_up_mem( x )
    y = y[ind]
    yn = yn[ind]
    x_neg = overlay_y_on_x(x, yn)
    x_neg = clean_up_mem( x_neg )

    net.layers[0].num_epochs = 1500 
    net.layers[1].num_epochs = 1500 
    net.layers[2].num_epochs = 1500 
    net.train(x_pos, x_neg)

    print('train error:', 1.0 - net.predict(x).eq(y).float().mean().item())

    x_te, y_te = next(iter(test_loader))
    #x_te, y_te = x_te.cuda(), y_te.cuda()
    x_te, y_te = x_te, y_te

    print('test error:', 1.0 - net.predict(x_te).eq(y_te).float().mean().item())
        
    for idx in range(len(net.layers)):
        plot_histograms(net, idx)
    
    
