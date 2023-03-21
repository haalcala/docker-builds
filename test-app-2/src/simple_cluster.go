package main

import (
	"encoding/json"
	"fmt"
	"sync"

	"github.com/hashicorp/memberlist"
)

var DEBUG_CLUSTER = true

type ClusterEvent string

type ClusterMessage struct {
	Event            string            `json:"event"`
	SendType         string            `json:"-"`
	WaitForAllToSend bool              `json:"-"`
	Data             []byte            `json:"data,omitempty"`
	Props            map[string]string `json:"props,omitempty"`
	Origin           string            `json:"origin,omitempty"`
	Id               int64             `json:"id,omitempty"`
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

func (s *SimpleCluster) startWithPort(hostname string, port int) (*eventDelegate, *memberlist.Memberlist, error) {
	fmt.Println("------ func startWithPort(port int) (*eventDelegate, *memberlist.Memberlist, error) port:", port)

	var m *memberlist.Memberlist

	broadcasts := &memberlist.TransmitLimitedQueue{
		NumNodes: func() int {
			return m.NumMembers()
		},
		RetransmitMult: 0,
	}

	s.broadcasts = broadcasts

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

	c.UDPBufferSize = 1024

	m, err := memberlist.Create(c)

	return _eventDelegate, m, err
}

func ToJSON(obj interface{}) []byte {
	_json, err := json.Marshal(obj)

	if err != nil {
		panic(err)
	}

	return _json
}

func (s *SimpleCluster) SendClusterMessage(msg *ClusterMessage) {
	if DEBUG_CLUSTER {
		fmt.Println("------ app/simple_cluster.go:: func (s *SimpleCluster) SendClusterMessage(msg *ClusterMessage)")
	}

	s.mtx.Lock()
	s.msgCounter += 1
	msg.Origin = s.clusterInfo.Id
	msg.Id = s.msgCounter
	s.mtx.Unlock()

	fmt.Println("------======>>>>>> msg:", string(ToJSON(msg)))

	// if s.redisClient != nil {
	// 	s.redisClient.Publish(context.TODO(), s.clusterDomain, ToJSON(msg))
	// }

	// u := &update{
	// 	Action: string(msg.Event),
	// 	Msg:    msg,
	// }

	// u.Data[this_node.Address()] = fmt.Sprintf("%v", s.start_time)

	// b, err := json.Marshal([]*update{u})

	b, err := json.Marshal(*msg)

	if err != nil {
		fmt.Println("Error encoding update into bytes")
		return
	}

	s.broadcasts.QueueBroadcast(&broadcast{
		msg:    append([]byte("d"), b...),
		notify: nil,
	})
}
