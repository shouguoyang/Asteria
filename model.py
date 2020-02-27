import torch
import torch.nn as nn
from torch.autograd import Variable

from ysg_treelstm import Tree


# module for childsumtreelstm
class ChildSumTreeLSTM(nn.Module):
    def __init__(self, voca_size, in_dim, mem_dim, device):
        super(ChildSumTreeLSTM, self).__init__()
        self.device = device
        self.in_dim = in_dim
        self.mem_dim = mem_dim
        self.emb = nn.Embedding(voca_size, self.in_dim).to(self.device)
        self.emb.weight.requires_grad = True
        self.ioux = nn.Linear(self.in_dim, 3 * self.mem_dim).to(self.device)
        self.iouh = nn.Linear(self.mem_dim, 3 * self.mem_dim).to(self.device)
        self.fx = nn.Linear(self.in_dim, self.mem_dim).to(self.device)
        self.fh = nn.Linear(self.mem_dim, self.mem_dim).to(self.device)

    def node_forward(self, inputs, child_c, child_h):
        child_h_sum = torch.sum(child_h, dim=0, keepdim=True)
        # child_h_sum = child_h_sum.to(self.device)
        iou = self.ioux(inputs) + self.iouh(child_h_sum)  #TODO 没有偏置 ？
        i, o, u = torch.split(iou, iou.size(1) // 3, dim=1)
        i, o, u = torch.sigmoid(i), torch.sigmoid(o), torch.tanh(u)
        f = torch.sigmoid(
            self.fh(child_h) +
            self.fx(inputs).repeat(len(child_h), 1)
        )
        fc = torch.mul(f, child_c)

        c = torch.mul(i, u) + torch.sum(fc, dim=0, keepdim=True)
        h = torch.mul(o, torch.tanh(c))
        return c, h

    def forward(self, tree):
        for idx in range(tree.num_children):
            self.forward(tree.children[idx])

        inputs = torch.LongTensor([tree.op]).to(self.device)
        inputs = self.emb(inputs)
        #TODO 加全连接层
        if tree.num_children == 0:
            # child_c = inputs[0].detach().new(1, self.mem_dim).fill_(0.).requires_grad_()
            # child_h = inputs[0].detach().new(1, self.mem_dim).fill_(0.).requires_grad_()

            #child_c = torch.Tensor(1, self.mem_dim).zero_().requires_grad_().to(self.device)
            child_c = torch.Tensor(1, self.mem_dim).new_ones(1,self.mem_dim).requires_grad_().to(self.device)
            #child_h = torch.Tensor(1, self.mem_dim).zero_().requires_grad_().to(self.device)
            child_h = torch.Tensor(1, self.mem_dim).new_ones(1, self.mem_dim).requires_grad_().to(self.device)
        else:
            child_c, child_h = zip(* map(lambda x: x.state, tree.children))
            child_c, child_h = torch.cat(child_c, dim=0), torch.cat(child_h, dim=0)

        tree.state = self.node_forward(inputs, child_c, child_h)
        del inputs, child_c, child_h
        return tree.state


# module for distance-angle similarity
class Similarity(nn.Module):
    def __init__(self, mem_dim, hidden_dim, num_classes, device):
        super(Similarity, self).__init__()
        self.device = device
        self.mem_dim = mem_dim
        self.hidden_dim = hidden_dim
        self.num_classes = num_classes
        self.wh = nn.Linear(2 * self.mem_dim, self.hidden_dim).to(self.device)
        self.wp = nn.Linear(self.hidden_dim, self.num_classes).to(self.device)
        self._out = nn.Linear(self.mem_dim, self.hidden_dim).to(self.device)
        # self._outt = nn.Linear(self.hidden_dim, 64).cuda()

    def forward(self, lvec, rvec): #二分类

        mult_dist = torch.mul(lvec, rvec)
        abs_dist = torch.abs(torch.add(lvec, -rvec))
        vec_dist = torch.cat((mult_dist, abs_dist), 1)

        out = torch.sigmoid(self.wh(vec_dist))
        out = torch.softmax(self.wp(out), dim=1)
        return out
        '''
        lout, rout = self._out(lvec), self._out(rvec)
        #lout, rout = self._outt(lout), self._outt(rout)
        MAB = torch.mul(torch.norm(lout).cuda(), torch.norm(rout).cuda()).cuda()
        AB = torch.dot(lout.squeeze(), rout.squeeze()).cuda()
        cos_similartiy = torch.div(torch.add(1, torch.div(AB, MAB).cuda()), 2)
        return torch.cat((torch.sub(1, cos_similartiy).unsqueeze(0), cos_similartiy.unsqueeze(0)))
        '''

# putting the whole model together
class SimilarityTreeLSTM(nn.Module):
    def __init__(self, vocab_size, in_dim, mem_dim, hidden_dim, num_classes, device):
        super(SimilarityTreeLSTM, self).__init__()
        # self.emb = nn.Embedding(vocab_size, in_dim, padding_idx=0, sparse=sparsity)
        # if freeze:
        #     self.emb.weight.requires_grad = False
        self.embmodel = ChildSumTreeLSTM(vocab_size, in_dim, mem_dim, device)
        self.similarity = Similarity(mem_dim, hidden_dim, num_classes, device)

    def forward(self, ltree, rtree):
        # linputs = self.emb(linputs)
        # rinputs = self.emb(rinputs)
        lstate, lhidden = self.embmodel(ltree)
        rstate, rhidden = self.embmodel(rtree)
        output = self.similarity(lstate, rstate)
        return output


def test_ChildSumTreeLSTM():
    from ysg_treelstm import Tree
    trees =[]
    for i in range(10,15):
        t = Tree()
        t.op = i
        trees.append(t)
    trees[0].add_child(trees[1])
    trees[0].add_child(trees[2])
    trees[2].add_child(trees[3])
    trees[2].add_child(trees[4])
    st = SimilarityTreeLSTM(80, 10, 16, 10, 2, torch.device("cpu"))
    root = trees[0]
    output = st(root,  root)
    print(output)



def test_detach():
    input = torch.Tensor([1])
    x = input.detach().new(1, 100).fill_(0.)
    y = x.requires_grad_()
    print(y)
if __name__ == '__main__':
    test_ChildSumTreeLSTM()
    # test_detach()