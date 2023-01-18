package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/hashicorp/memberlist"
)

type ClusterMessage struct {
	Id int64
}

type ClusterInfo struct {
	Id         string `json:"id"`
	Version    string `json:"version"`
	ConfigHash string `json:"config_hash"`
	IPAddress  string `json:"ipaddress"`
	Hostname   string `json:"hostname"`
}

type SimpleCluster struct {
	clusterDomain string

	clusterInfo *ClusterInfo

	clusterInfos map[string]*ClusterInfo

	mtx        sync.RWMutex
	items      map[string]int64
	broadcasts *memberlist.TransmitLimitedQueue

	this_node *memberlist.Node

	start_time int64

	eventDelegate *eventDelegate

	isMaster bool

	initialised bool

	isReady bool

	stopping bool
	stopped  bool

	memberlist *memberlist.Memberlist

	msgCounter int64
}

type eventDelegate struct {
	nodes    []string
	items    *map[string]int64
	delegate *delegate
}

type broadcast struct {
	msg    []byte
	notify chan<- struct{}
}

type delegate struct {
	mtx        *sync.RWMutex
	items      *map[string]int64
	broadcasts *memberlist.TransmitLimitedQueue
	cluster    *SimpleCluster
}

type update struct {
	Action string // add, del
	Data   *map[string]string
	Msg    *ClusterMessage
}

type members_data struct {
	Timestamp int64
	Members   map[string]int64
	Remarks   string
}

func (b *broadcast) Invalidates(other memberlist.Broadcast) bool {
	// fmt.Println("------ func (b *broadcast) Invalidates(other memberlist.Broadcast) bool:: other:", string(other.Message()))

	return true
}

func (b *broadcast) Message() []byte {
	// fmt.Println("------ func (b *broadcast) Message() []byte")

	return b.msg
}

func (b *broadcast) Finished() {
	// fmt.Println("------ func (b *broadcast) Finished()")

	if b.notify != nil {
		close(b.notify)
	}
}

func (d *delegate) NodeMeta(limit int) []byte {
	fmt.Println("------ func (d *delegate) NodeMeta(limit int) []byte")

	return []byte{}
}

func (d *delegate) NotifyMsg(b []byte) {
	// fmt.Println("------ func (d *delegate) NotifyMsg(b []byte)")
	fmt.Println("------ func (d *delegate) NotifyMsg:: b:", string(b))

	if len(b) == 0 {
		return
	}

	switch b[0] {
	case 'd': // data
		var payload *update

		if err := json.Unmarshal(b[1:], &payload); err != nil {
			return
		}
		d.mtx.Lock()
		if payload.Data != nil {
			for k, v := range *payload.Data {
				switch payload.Action {
				case "add":
					_v, _ := strconv.ParseInt(v, 10, 64)
					(*d.items)[k] = _v
				case "del":
					delete(*d.items, k)
				}
			}
		}
		d.mtx.Unlock()
	}
}

func (d *delegate) GetBroadcasts(overhead, limit int) [][]byte {
	broadcasts := d.broadcasts.GetBroadcasts(overhead, limit)

	if len(broadcasts) == 0 {
		return nil
	}

	// fmt.Println("------ func (d *delegate) GetBroadcasts(overhead, limit int) [][]byte")

	// fmt.Println("broadcasts:", broadcasts, "len(broadcasts):", len(broadcasts))

	// for b := range broadcasts {
	// 	fmt.Println("b:", string(broadcasts[b]))
	// }

	return broadcasts
}

func (d *delegate) LocalState(join bool) []byte {
	// fmt.Println("------ func (d *delegate) LocalState(join bool) []byte: join:", join, "d.items:", d.items)

	d.mtx.RLock()

	m := members_data{
		Timestamp: time.Now().UnixMilli(),
		Members:   *d.items,
		Remarks:   d.cluster.clusterInfo.Id,
	}
	d.mtx.RUnlock()

	b, _ := json.Marshal(m)

	// fmt.Println("------ func (d *delegate) LocalState: <<------- b:", string(b))

	return b
}

func (d *delegate) MergeRemoteState(buf []byte, join bool) {
	// fmt.Println("------ func (d *delegate) MergeRemoteState(buf []byte, join bool) buff:", string(buf), "join:", join)

	if len(buf) == 0 {
		return
	}
	if !join {
		return
	}
	var m members_data

	if err := json.Unmarshal(buf, &m); err != nil {
		return
	}

	d.mtx.Lock()
	// fmt.Println("d.items:", d.items)
	for k, v := range m.Members {
		fmt.Println("k:", k, "v:", v)
		(*d.items)[k] = v
	}
	// fmt.Println("d.items:", d.items)
	d.mtx.Unlock()
}

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

func (s *SimpleCluster) startWithPort(hostname string, port int) (*eventDelegate, *memberlist.Memberlist, error) {
	fmt.Println("------ func startWithPort(port int) (*eventDelegate, *memberlist.Memberlist, error) port:", port)

	var m *memberlist.Memberlist

	broadcasts := &memberlist.TransmitLimitedQueue{
		NumNodes: func() int {
			return m.NumMembers()
		},
		RetransmitMult: 0,
	}

	_delegate := &delegate{
		mtx:        &s.mtx,
		items:      &s.items,
		cluster:    s,
		broadcasts: broadcasts,
	}

	_eventDelegate := &eventDelegate{
		nodes:    []string{},
		items:    &s.items,
		delegate: _delegate,
	}

	c := memberlist.DefaultLocalConfig()
	c.Events = _eventDelegate
	c.Delegate = _delegate
	// c.BindPort = 0
	// c.Name = hostname + "-" + uuid.NewUUID().String()
	c.Name = hostname
	c.BindPort = port

	m, err := memberlist.Create(c)

	return _eventDelegate, m, err
}

func main() {

	start_time := time.Now().Unix()

	s := &SimpleCluster{
		items:       map[string]int64{},
		start_time:  start_time,
		initialised: false,
		isReady:     false,
		stopping:    false,
		stopped:     false,
	}

	fmt.Println("pid:", os.Getpid())

	hostname, err := os.Hostname()

	if err != nil {
		panic(err)
	}

	clusterInfo := &ClusterInfo{
		Hostname: hostname,
		Id:       fmt.Sprintf("%v-%v", hostname, os.Getpid()),
		// IPAddress: ip.String(),
	}

	bind_port, err := strconv.Atoi(os.Getenv("TEST_APP_2_BIND_PORT"))

	if err != nil {
		panic(err)
	}

	eventDelegate, m, err := s.startWithPort(clusterInfo.Id, bind_port)

	if err != nil {
		panic(err)
	}

	s.memberlist = m
	s.eventDelegate = eventDelegate

	this_node := m.LocalNode()
	s.this_node = this_node

	s.items[this_node.Address()] = s.start_time

	clusterInfo.IPAddress = this_node.Address()

}
