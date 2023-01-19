package main

import (
	"fmt"

	"github.com/hashicorp/memberlist"
)

func (ed *eventDelegate) NotifyJoin(node *memberlist.Node) {
	fmt.Println("------ func (ed *eventDelegate) NotifyJoin(node *memberlist.Node)")

	fmt.Println("A node has joined: "+node.String(), "node.FullAddress().Addr:", node.FullAddress().Addr)

	ed.nodes = append(ed.nodes, node.FullAddress().Addr)

	fmt.Println("ed.nodes:", ed.nodes)
}

func remove(slice []string, s int) []string {
	fmt.Println("------ func remove(slice []string, s int) []string")

	return append(slice[:s], slice[s+1:]...)
}

func (ed *eventDelegate) NotifyLeave(node *memberlist.Node) {
	fmt.Println("------ func (ed *eventDelegate) NotifyLeave(node *memberlist.Node)")

	fmt.Println("A node has left: "+node.String(), node.FullAddress().Addr)

	index := -1

	for ni, n := range ed.nodes {
		if n == node.FullAddress().Addr {
			index = ni
		}
	}

	if index >= 0 {
		ed.nodes = remove(ed.nodes, index)
	}

	fmt.Println("ed.nodes:", ed.nodes)

	for i := range *ed.items {
		fmt.Println("i:", i)

		if i == node.FullAddress().Addr {
			fmt.Println("Removing", node.FullAddress().Addr, "from list")
			delete(*ed.items, i)
		}
	}
}

func (ed *eventDelegate) NotifyUpdate(node *memberlist.Node) {
	fmt.Println("------ func (ed *eventDelegate) NotifyUpdate(node *memberlist.Node)")

	fmt.Println("A node was updated: " + node.String())
}
