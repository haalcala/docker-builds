package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hashicorp/memberlist"
)

func (b *broadcast) Invalidates(other memberlist.Broadcast) bool {
	fmt.Println("------ func (b *broadcast) Invalidates(other memberlist.Broadcast) bool:: other:", string(other.Message()))

	return false
}

func (b *broadcast) Message() []byte {
	fmt.Println("------ func (b *broadcast) Message() []byte")

	return b.msg
}

func (b *broadcast) Finished() {
	fmt.Println("------ func (b *broadcast) Finished()")

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

	// if len(b) == 0 {
	// 	return
	// }

	// switch b[0] {
	// case 'd': // data
	// 	var payload *update

	// 	if err := json.Unmarshal(b[1:], &payload); err != nil {
	// 		return
	// 	}
	// 	d.mtx.Lock()
	// 	if payload.Data != nil {
	// 		for k, v := range *payload.Data {
	// 			switch payload.Action {
	// 			case "add":
	// 				_v, _ := strconv.ParseInt(v, 10, 64)
	// 				(*d.items)[k] = _v
	// 			case "del":
	// 				delete(*d.items, k)
	// 			}
	// 		}
	// 	}
	// 	d.mtx.Unlock()
	// }
}

func (d *delegate) GetBroadcasts(overhead, limit int) [][]byte {
	fmt.Println("------ func (d *delegate) GetBroadcasts(overhead, limit int) [][]byte overhead:", overhead, "limit:", limit)
	broadcasts := d.broadcasts.GetBroadcasts(overhead, limit)

	if len(broadcasts) == 0 {
		return nil
	}

	fmt.Println("broadcasts:", broadcasts, "len(broadcasts):", len(broadcasts))

	_broadcasts := [][]byte{}

	for b := range broadcasts {
		// fmt.Println("b:", b, string(broadcasts[b]))
		fmt.Println("b:", b, string(broadcasts[len(broadcasts)-b-1]))

		_broadcasts = append(_broadcasts, broadcasts[len(broadcasts)-b-1])
	}

	return _broadcasts
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
